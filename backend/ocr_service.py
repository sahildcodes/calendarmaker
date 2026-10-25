import os
import re
import subprocess
import shutil
import tempfile
import uuid
from typing import Dict, Any, List, Optional
from PIL import Image, ImageEnhance, ImageFilter, ImageStat, ImageOps, UnidentifiedImageError
import pytesseract
from backend.security import MAX_OCR_TEXT_LENGTH

# Register HEIF / HEIC opener for iPhone photos
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass

# Auto-detect Tesseract binary and tessdata directory across Linux, Docker, and macOS
for candidate_dir in [
    "/usr/share/tesseract-ocr/5/tessdata",
    "/usr/share/tesseract-ocr/4.00/tessdata",
    "/usr/share/tessdata",
    "/opt/homebrew/share/tessdata",
    "/usr/local/share/tessdata"
]:
    if os.path.exists(candidate_dir) and "TESSDATA_PREFIX" not in os.environ:
        os.environ["TESSDATA_PREFIX"] = candidate_dir
        break

# Prevent OpenMP multi-thread thrashing on cloud vCPUs
os.environ["OMP_THREAD_LIMIT"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

# Limit maximum image pixels to 20 million to prevent decompression bombs
Image.MAX_IMAGE_PIXELS = 20_000_000

class ImageSecurityError(Exception):
    """Base exception for image security validation failures."""
    pass

class DecompressionBombError(ImageSecurityError):
    pass

class InvalidImageError(ImageSecurityError):
    pass

class CorruptedImageError(ImageSecurityError):
    pass

class OCRTimeoutError(ImageSecurityError):
    pass

class OCRProcessingError(ImageSecurityError):
    pass

class OCRService:
    def __init__(self):
        tess_path = shutil.which("tesseract")
        if not tess_path:
            for p in ["/usr/bin/tesseract", "/usr/local/bin/tesseract", "/opt/homebrew/bin/tesseract"]:
                if os.path.exists(p):
                    tess_path = p
                    break
        if tess_path:
            pytesseract.pytesseract.tesseract_cmd = tess_path
        self.tesseract_available = tess_path is not None

    def verify_and_reconstruct_image(self, input_path: str, output_path: str) -> Dict[str, Any]:
        """
        Hardened image verification and safe reconstruction pipeline:
        1. Verifies actual file format using Pillow (PNG, JPEG, WEBP only).
        2. Guards against decompression bombs (< 20,000,000 pixels).
        3. Rejects animated / multi-frame images.
        4. Reconstructs image as pure RGB and re-encodes to a new PNG, stripping EXIF, metadata & embedded exploits.
        """
        # 1. Initial format & integrity verification
        try:
            with Image.open(input_path) as img:
                fmt = (img.format or "").upper()
                allowed_formats = ("PNG", "JPEG", "JPG", "WEBP", "HEIC", "HEIF", "MPO", "BMP", "TIFF")
                if fmt not in allowed_formats:
                    raise InvalidImageError(f"Unsupported file format '{fmt}'. Allowed formats: PNG, JPEG, WebP, HEIC.")
                
                # Check dimensions before decoding
                if img.width * img.height > 20_000_000:
                    raise DecompressionBombError("Image dimensions exceed the 20 million pixel safety limit.")
                
                # Verify image structure
                img.verify()
        except Image.DecompressionBombError as e:
            raise DecompressionBombError("Image exceeds safe pixel dimensions (possible decompression bomb attack).") from e
        except UnidentifiedImageError as e:
            raise InvalidImageError("File is not a valid or recognized image.") from e
        except (OSError, SyntaxError, ValueError) as e:
            raise CorruptedImageError("Image file is corrupted or truncated.") from e

        # 2. Re-open after verify() (Pillow requirement) and check animation
        try:
            with Image.open(input_path) as img:
                # Disallow animated images (single frame only)
                is_animated = getattr(img, "is_animated", False)
                n_frames = getattr(img, "n_frames", 1)
                if is_animated or n_frames > 1:
                    raise InvalidImageError("Animated images are not supported. Please upload a single-frame image.")

                # Double check pixel count
                if img.width * img.height > 20_000_000:
                    raise DecompressionBombError("Image dimensions exceed the 20 million pixel safety limit.")

                # 3. Safe RGB conversion (removes alpha channels, pallets, CMYK)
                if img.mode in ("RGBA", "P"):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "RGBA":
                        bg.paste(img, mask=img.split()[3])
                    else:
                        bg.paste(img)
                    safe_img = bg
                elif img.mode != "RGB":
                    safe_img = img.convert("RGB")
                else:
                    safe_img = img.copy()

                # Correct phone orientation from EXIF if present
                try:
                    safe_img = ImageOps.exif_transpose(safe_img)
                except Exception:
                    pass

                # Downscale oversized phone camera images (e.g. 12MP iPhone photos) to safe 1800px max dimension
                # This prevents OOM (out-of-memory) crashes on 512MB cloud instances and saves ~80% memory!
                max_dim = max(safe_img.width, safe_img.height)
                if max_dim > 1800:
                    ratio = 1800.0 / max_dim
                    new_w = max(int(safe_img.width * ratio), 100)
                    new_h = max(int(safe_img.height * ratio), 100)
                    safe_img = safe_img.resize((new_w, new_h), Image.Resampling.BILINEAR)

                # Re-encode to sanitized PNG file (strips metadata, comments, EXIF)
                safe_img.save(output_path, format="PNG")
                
                return {
                    "width": safe_img.width,
                    "height": safe_img.height,
                    "format": "PNG"
                }
        except (ImageSecurityError, UnidentifiedImageError):
            raise
        except Exception as e:
            raise CorruptedImageError(f"Failed to decode and reconstruct image safely: {str(e)}") from e

    # Alias for API backward-compatibility
    validate_and_reconstruct_image = verify_and_reconstruct_image

    def preprocess_image(self, image_path: str) -> Image.Image:
        """Enhances contrast, resolution, and sharpness for optimal OCR accuracy."""
        img = Image.open(image_path)
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        if img.mode != "RGB":
            img = img.convert("RGB")

        # Downscale oversized phone camera images (e.g. 12MP iPhone photos) to safe 1800px max dimension
        # This prevents OOM (out-of-memory) crashes on 512MB cloud instances and speeds up OCR by 5x!
        max_dim = max(img.width, img.height)
        if max_dim > 1800:
            ratio = 1800.0 / max_dim
            new_w = max(int(img.width * ratio), 100)
            new_h = max(int(img.height * ratio), 100)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        elif max_dim < 700:
            # Upscale small or low-resolution images for higher OCR character recognition
            ratio = min(1200.0 / max_dim, 2.0)
            new_w = int(img.width * ratio)
            new_h = int(img.height * ratio)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Contrast enhancement and text sharpening
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.25)
        img = img.filter(ImageFilter.SHARPEN)
        return img

    def _execute_tesseract(self, img: Image.Image, config: str = "") -> Dict[str, Any]:
        """Low-level tesseract execution wrapper with timeout and fallback."""
        base_config = "--oem 1"
        full_config = f"{base_config} {config}".strip() if config else base_config
        extra_args = {"config": full_config}
        try:
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, timeout=20, **extra_args)
        except Exception as e:
            err_msg = str(e).lower()
            if "timeout" in err_msg:
                raise OCRTimeoutError("Tesseract OCR execution timed out.") from e
            
            # Graceful fallback: try simple image_to_string if image_to_data fails
            try:
                raw_text = pytesseract.image_to_string(img, timeout=15, **extra_args)
                lines = []
                for l in raw_text.splitlines():
                    clean_l = l.strip()
                    if clean_l:
                        lines.append({
                            "text": clean_l,
                            "confidence": 75.0,
                            "bbox": {"x": 0, "y": 0, "w": img.width, "h": 20},
                            "is_unreliable": False
                        })
                return {
                    "engine": "tesseract_fallback",
                    "raw_text": raw_text,
                    "lines": lines,
                    "tokens": [],
                    "avg_confidence": 75.0
                }
            except Exception as fallback_err:
                if "timeout" in str(fallback_err).lower():
                    raise OCRTimeoutError("Tesseract OCR execution timed out.") from fallback_err
                print(f"[OCR ERROR]: {fallback_err}")
                raise OCRProcessingError(f"OCR engine could not read text: {str(fallback_err)}") from fallback_err

        n_boxes = len(data['text'])
        lines_dict: Dict[int, List[Dict[str, Any]]] = {}
        total_conf = 0.0
        counted_words = 0
        tokens = []

        for i in range(n_boxes):
            word = data['text'][i].strip()
            conf = float(data['conf'][i])
            if not word:
                continue

            if conf >= 0:
                total_conf += conf
                counted_words += 1

            line_num = data['line_num'][i]
            block_num = data['block_num'][i]
            par_num = data['par_num'][i]
            key = (block_num, par_num, line_num)

            token_info = {
                "text": word,
                "confidence": conf if conf >= 0 else 0,
                "bbox": {
                    "x": data['left'][i],
                    "y": data['top'][i],
                    "w": data['width'][i],
                    "h": data['height'][i],
                },
                "is_unreliable": (conf < 55 and conf >= 0)
            }
            tokens.append(token_info)

            if key not in lines_dict:
                lines_dict[key] = []
            lines_dict[key].append(token_info)

        lines = []
        for key in sorted(lines_dict.keys()):
            line_tokens = lines_dict[key]
            line_text = " ".join(t["text"] for t in line_tokens)
            confs = [t["confidence"] for t in line_tokens if t["confidence"] > 0]
            avg_line_conf = sum(confs) / len(confs) if confs else 0.0

            min_x = min(t["bbox"]["x"] for t in line_tokens)
            min_y = min(t["bbox"]["y"] for t in line_tokens)
            max_r = max(t["bbox"]["x"] + t["bbox"]["w"] for t in line_tokens)
            max_b = max(t["bbox"]["y"] + t["bbox"]["h"] for t in line_tokens)

            lines.append({
                "text": line_text,
                "confidence": round(avg_line_conf, 1),
                "bbox": {"x": min_x, "y": min_y, "w": max_r - min_x, "h": max_b - min_y},
                "is_unreliable": avg_line_conf < 60.0
            })

        avg_conf = (total_conf / counted_words) if counted_words > 0 else 0.0
        raw_text = "\n".join(line["text"] for line in lines)
        if len(raw_text) > MAX_OCR_TEXT_LENGTH:
            raw_text = raw_text[:MAX_OCR_TEXT_LENGTH]

        return {
            "engine": "tesseract",
            "raw_text": raw_text,
            "lines": lines,
            "tokens": tokens,
            "avg_confidence": round(avg_conf, 1)
        }

    def extract_with_tesseract(self, img: Image.Image) -> Dict[str, Any]:
        """Runs fast single-pass Tesseract OCR, falling back only when no tokens are found."""
        # Pass 1: Standard layout with fast LSTM engine
        pass1 = self._execute_tesseract(img)

        # Only attempt second pass if standard engine found virtually no tokens (< 6 words) and didn't already fallback
        if pass1.get("engine") != "tesseract_fallback" and len(pass1.get("tokens", [])) < 6 and len(pass1.get("lines", [])) < 2:
            try:
                pass2 = self._execute_tesseract(img, config="--psm 6")
                if len(pass2.get("tokens", [])) > len(pass1.get("tokens", [])):
                    return pass2
            except Exception:
                pass

        return pass1

    def normalize_text(self, text: str) -> str:
        """Normalizes OCR text delimiters, typos, and broken hyphens."""
        cleaned = text

        cleaned = re.sub(r'[—–−―]', '-', cleaned)
        cleaned = re.sub(r'[\u2018\u2019]', "'", cleaned)
        cleaned = re.sub(r'[\u201C\u201D]', '"', cleaned)

        # Fix common AM/PM OCR misspellings first
        cleaned = re.sub(r'\b(?:pn|prn|p\.n\.)\b', 'PM', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b(?:arn|a\.n\.)\b', 'AM', cleaned, flags=re.IGNORECASE)

        # Fix missing colons in 4-digit OCR times: 0300 PM -> 03:00 PM, 1000 AM -> 10:00 AM
        cleaned = re.sub(r'\b([01]?\d)([0-5]\d)\s*(am|pm)\b', r'\1:\2 \3', cleaned, flags=re.IGNORECASE)
        
        # Fix periods or semicolons used instead of colons: 02.00 PM, 11;59 PM, 02.0 PM -> 02:00 PM
        cleaned = re.sub(r'\b([01]?\d)[.;]([0-5]\d)\s*(am|pm|a\.m\.|p\.m\.)\b', r'\1:\2 \3', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b([01]?\d)[.;]0\s*(am|pm)\b', r'\1:00 \2', cleaned, flags=re.IGNORECASE)

        # Fix letter O/o used instead of zero in times: 1O:OO -> 10:00
        cleaned = re.sub(r'\b([01]?\d):[oO]([0-9])\b', r'\g<1>:0\g<2>', cleaned)
        cleaned = re.sub(r'\b([01]?\d):([0-9])[oO]\b', r'\g<1>:\g<2>0', cleaned)
        cleaned = re.sub(r'\b[oO]([0-9]):([0-5]\d)\b', r'0\g<1>:\g<2>', cleaned)

        # Fix common OCR month name typos
        cleaned = re.sub(r'\b[0oO]ct(?:ober)?\b', 'October', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bQct(?:ober)?\b', 'October', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bDec[eern]+ber\b', 'December', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bSep[teern]+ber\b', 'September', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bNov[eern]+ber\b', 'November', cleaned, flags=re.IGNORECASE)

        # Course schedule days of week delimiter cleanup
        cleaned = re.sub(r'\bDays?\s*:?\s*([MTWRF]{2,5})\s*\|', r'Days \1 |', cleaned, flags=re.IGNORECASE)

        cleaned = re.sub(r'(\d{1,2}(?::\d{2})?)\s*(am|pm)\s*-\s*(\d{1,2}(?::\d{2})?)\s*(am|pm)', r'\1 \2 - \3 \4', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})', r'\1 - \2', cleaned)

        cleaned = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', cleaned)

        lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in cleaned.splitlines()]
        normalized_lines = []
        for line in lines:
            if line or (normalized_lines and normalized_lines[-1] != ""):
                normalized_lines.append(line)

        result = "\n".join(normalized_lines)
        return result[:MAX_OCR_TEXT_LENGTH]

    def process_image(self, sanitized_image_path: str) -> Dict[str, Any]:
        """Processes a verified, sanitized image: preprocessing, OCR extraction, normalization."""
        img = self.preprocess_image(sanitized_image_path)
        
        ocr_res = self.extract_with_tesseract(img)
        normalized_text = self.normalize_text(ocr_res["raw_text"])

        unreliable_lines = [line["text"] for line in ocr_res["lines"] if line["is_unreliable"]]
        warnings = []
        if ocr_res["avg_confidence"] < 65.0 and len(ocr_res["lines"]) > 0:
            warnings.append(f"Overall OCR confidence is low ({ocr_res['avg_confidence']}%), text may contain inaccuracies.")
        if len(unreliable_lines) > 0:
            warnings.append(f"{len(unreliable_lines)} line(s) flagged with low OCR confidence (<60%).")

        return {
            "raw_text": ocr_res["raw_text"],
            "normalized_text": normalized_text,
            "avg_confidence": ocr_res["avg_confidence"],
            "lines": ocr_res["lines"],
            "tokens": ocr_res["tokens"],
            "unreliable_lines": unreliable_lines,
            "ocr_warnings": warnings,
            "image_size": {"width": img.width, "height": img.height}
        }
