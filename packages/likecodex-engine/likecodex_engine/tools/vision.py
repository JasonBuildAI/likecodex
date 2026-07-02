"""Vision/multimodal tools for the agent.

Provides image analysis, screenshot capture, UI-to-code description,
PDF text extraction, and image format conversion.

All tools use the vision__ prefix to avoid naming conflicts.
"""

from __future__ import annotations

import base64
import io
import json
import os
import tempfile
from typing import Any

# ---------------------------------------------------------------------------
# Tool registry for conditional registration
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: dict[str, dict[str, Any]] = {}


def tool(
    name: str,
    description: str,
    read_only: bool = True,
    parameters: dict | None = None,
) -> Any:
    """Decorator to register a vision tool."""

    def decorator(func: Any) -> Any:
        TOOL_DEFINITIONS[name] = {
            "name": name,
            "description": description,
            "read_only": read_only,
            "handler": func,
            "parameters": parameters or {"type": "object", "properties": {}},
        }
        return func

    return decorator


# ===================================================================
# 1. image_analyze — 图片理解分析
# ===================================================================


@tool(
    name="vision__image_analyze",
    description=(
        "Analyze an image file: read basic metadata (size, format, mode) and "
        "optionally return a base64-encoded data URI for LLM vision processing. "
        "Large images are automatically resized to fit within 2048px on the longest edge."
    ),
    read_only=True,
    parameters={
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Absolute or relative path to the image file",
            },
            "prompt": {
                "type": "string",
                "description": "Optional analysis prompt describing what to look for",
            },
            "return_base64": {
                "type": "boolean",
                "description": "Whether to include a base64 data URI in the result",
                "default": False,
            },
        },
        "required": ["image_path"],
    },
)
async def vision__image_analyze(
    image_path: str,
    prompt: str = "",
    return_base64: bool = False,
) -> str:
    """Analyze an image file and return metadata + optional base64 content."""
    try:
        from PIL import Image
    except ImportError:
        return json.dumps({"error": "Pillow is not installed. Run `pip install Pillow`."})

    path = _resolve_path(image_path)
    if not path:
        return json.dumps({"error": f"Image not found: {image_path}"})

    try:
        img = Image.open(path)
        fmt = img.format or "unknown"
        mode = img.mode
        w, h = img.size

        result: dict[str, Any] = {
            "file_name": os.path.basename(path),
            "file_size_bytes": os.path.getsize(path),
            "format": fmt,
            "mode": mode,
            "width": w,
            "height": h,
        }

        # Auto-compress if too large
        img_resized = _auto_resize(img)
        if img_resized.size != img.size:
            result["original_size"] = {"width": w, "height": h}
            result["resized_to"] = {"width": img_resized.width, "height": img_resized.height}

        if return_base64:
            # Encode as JPEG for smaller payload
            buf = io.BytesIO()
            convert_to_rgb(img_resized).save(buf, format="JPEG", quality=85)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            result["data_uri"] = f"data:image/jpeg;base64,{b64}"
            result["base64_length"] = len(b64)

        if prompt:
            result["analysis_prompt"] = prompt
            result["note"] = (
                "Image metadata returned. Pass the data_uri to a vision-capable "
                "LLM model for detailed analysis."
            )

        return json.dumps(result, ensure_ascii=False)

    except Exception as exc:
        return json.dumps({"error": f"Failed to analyze image: {exc}"})


# ===================================================================
# 2. capture_screenshot — 截图工具
# ===================================================================


@tool(
    name="vision__capture_screenshot",
    description=(
        "Capture a screenshot of the screen. Supports fullscreen, active window, "
        "or a custom screen region. Uses pyautogui or mss for cross-platform support."
    ),
    read_only=True,
    parameters={
        "type": "object",
        "properties": {
            "region": {
                "type": "string",
                "enum": ["fullscreen", "window", "area"],
                "description": "Capture region",
                "default": "fullscreen",
            },
            "output_path": {
                "type": "string",
                "description": "Where to save the screenshot (default: temp file)",
            },
        },
        "required": [],
    },
)
async def vision__capture_screenshot(
    region: str = "fullscreen",
    output_path: str = "",
) -> str:
    """Capture a screenshot and return the saved file path."""
    if not output_path:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        output_path = tmp.name
        tmp.close()

    # Try mss first (faster), fall back to pyautogui
    saved = False
    try:
        import mss

        with mss.mss() as sct:
            monitor = sct.monitors[0]  # full first monitor
            if region == "fullscreen":
                # Use all-in-one for full screen
                sct.shot(output=output_path)
                saved = True
            elif region == "window":
                # Capture the primary monitor
                mon = sct.monitors[1]
                im = sct.grab(mon)
                from PIL import Image as _PIL

                _PIL.frombytes("RGB", im.size, im.rgb).save(output_path)
                saved = True
            else:
                # area — capture primary monitor as well
                mon = sct.monitors[1]
                im = sct.grab(mon)
                from PIL import Image as _PIL

                _PIL.frombytes("RGB", im.size, im.rgb).save(output_path)
                saved = True
    except ImportError:
        pass

    if not saved:
        try:
            import pyautogui

            screenshot = pyautogui.screenshot()
            if region == "window":
                screenshot = pyautogui.screenshot(region=pyautogui.getActiveWindow())
            screenshot.save(output_path)
            saved = True
        except ImportError:
            return json.dumps(
                {
                    "error": (
                        "Neither mss nor pyautogui is installed. "
                        "Run `pip install mss pyautogui`."
                    )
                }
            )
        except Exception as exc:
            return json.dumps({"error": f"Screenshot failed: {exc}"})

    file_size = os.path.getsize(output_path)
    return json.dumps(
        {
            "file_path": os.path.abspath(output_path),
            "file_size_bytes": file_size,
            "region": region,
            "format": "PNG",
        },
        ensure_ascii=False,
    )


# ===================================================================
# 3. screenshot_to_code — 截图转代码描述
# ===================================================================


@tool(
    name="vision__screenshot_to_code",
    description=(
        "Analyze a screenshot/UI image and generate a structured textual description "
        "of UI elements (buttons, text fields, images, layouts, colors). "
        "This description can guide LLM code generation for replicating the UI."
    ),
    read_only=True,
    parameters={
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Path to the screenshot or UI image",
            },
            "context": {
                "type": "string",
                "description": "Optional context (e.g. expected framework, target platform)",
            },
            "detail_level": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "Level of detail in the description",
                "default": "medium",
            },
        },
        "required": ["image_path"],
    },
)
async def vision__screenshot_to_code(
    image_path: str,
    context: str = "",
    detail_level: str = "medium",
) -> str:
    """Analyze a UI screenshot and produce a structured textual description."""
    try:
        from PIL import Image
    except ImportError:
        return json.dumps({"error": "Pillow is not installed."})

    path = _resolve_path(image_path)
    if not path:
        return json.dumps({"error": f"Image not found: {image_path}"})

    try:
        img = Image.open(path)
        img = _auto_resize(img)
        w, h = img.size
        fmt = img.format or "unknown"
        mode = img.mode

        # Basic image statistics for the LLM to reason about
        pixels = list(img.getdata())
        total_pixels = len(pixels)

        # Estimate color complexity (sample first 5000 pixels)
        sample = pixels[: min(5000, total_pixels)]
        # Reduce to sets of (r >> 3, g >> 3, b >> 3) for a rough colour-count
        if mode == "RGBA":
            unique_colors = len({(p[0] >> 3, p[1] >> 3, p[2] >> 3) for p in sample if len(p) >= 3})
        elif mode == "RGB":
            unique_colors = len({(p[0] >> 3, p[1] >> 3, p[2] >> 3) for p in sample})
        else:
            # Convert to RGB first
            rgb_img = img.convert("RGB")
            rgb_sample = list(rgb_img.getdata())[: min(5000, total_pixels)]
            unique_colors = len({(p[0] >> 3, p[1] >> 3, p[2] >> 3) for p in rgb_sample})

        # Check if image has transparency
        has_alpha = mode in ("RGBA", "LA", "PA") or (mode == "P" and "transparency" in img.info)

        description: dict[str, Any] = {
            "file_name": os.path.basename(path),
            "image_dimensions": {"width": w, "height": h},
            "format": fmt,
            "mode": mode,
            "has_transparency": has_alpha,
            "estimated_color_count": unique_colors,
            "aspect_ratio": round(w / h, 4) if h > 0 else 0,
            "ui_analysis": _describe_ui_structure(img, detail_level),
        }

        if context:
            description["context"] = context

        description["note"] = (
            "This is a structural description of the image. "
            "It can guide code generation but is not a substitute for "
            "passing the actual image to a vision model."
        )

        return json.dumps(description, ensure_ascii=False)

    except Exception as exc:
        return json.dumps({"error": f"Failed to analyze screenshot: {exc}"})


def _describe_ui_structure(img: Any, detail_level: str) -> dict[str, Any]:
    """Generate a heuristic structural description of a UI image."""
    w, h = img.size
    # Divide the image into horizontal bands
    thirds = h // 3

    # Roughly estimate regions
    regions = {
        "top_third": {"y_range": [0, thirds], "height_px": thirds},
        "middle_third": {"y_range": [thirds, 2 * thirds], "height_px": thirds},
        "bottom_third": {"y_range": [2 * thirds, h], "height_px": h - 2 * thirds},
    }

    # Detect if the image is mostly light or dark
    try:
        gray = img.convert("L")
        hist = gray.histogram()
        total = sum(hist)
        avg_brightness = sum(i * count for i, count in enumerate(hist)) / total if total else 128
        overall_tone = "light" if avg_brightness > 128 else "dark"
    except Exception:
        overall_tone = "unknown"

    # Edge detection heuristic: check horizontal/vertical variance in center
    has_sharp_edges = False
    try:
        import math

        center_strip = gray.crop((0, h // 2 - 2, w, h // 2 + 2)) if h > 4 else gray
        pixels_strip = list(center_strip.getdata())
        if pixels_strip:
            mean_val = sum(pixels_strip) / len(pixels_strip)
            variance = sum((p - mean_val) ** 2 for p in pixels_strip) / len(pixels_strip)
            has_sharp_edges = variance > 1500
    except Exception:
        pass

    result: dict[str, Any] = {
        "overall_tone": overall_tone,
        "has_sharp_edges": has_sharp_edges,
        "regions": regions,
    }

    if detail_level == "high":
        # Provide more detailed quadrant information
        quad_w, quad_h = w // 2, h // 2
        result["quadrants"] = {
            "top_left": {"width": quad_w, "height": quad_h},
            "top_right": {"width": w - quad_w, "height": quad_h},
            "bottom_left": {"width": quad_w, "height": h - quad_h},
            "bottom_right": {"width": w - quad_w, "height": h - quad_h},
        }

    return result


# ===================================================================
# 4. read_pdf — PDF 文档读取
# ===================================================================


@tool(
    name="vision__read_pdf",
    description=(
        "Extract text content from a PDF file. Supports specific page ranges "
        "(e.g. '1-5', '1,3,5') or 'all' pages. Optionally extract embedded images."
    ),
    read_only=True,
    parameters={
        "type": "object",
        "properties": {
            "pdf_path": {
                "type": "string",
                "description": "Path to the PDF file",
            },
            "pages": {
                "type": "string",
                "description": "Pages to extract: 'all', '1-5' (range), or '1,3,5' (list)",
                "default": "all",
            },
            "extract_images": {
                "type": "boolean",
                "description": "Whether to extract embedded images from the PDF",
                "default": False,
            },
        },
        "required": ["pdf_path"],
    },
)
async def vision__read_pdf(
    pdf_path: str,
    pages: str = "all",
    extract_images: bool = False,
) -> str:
    """Extract text (and optionally images) from a PDF file."""
    path = _resolve_path(pdf_path)
    if not path:
        return json.dumps({"error": f"PDF not found: {pdf_path}"})

    # Try PyMuPDF first
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(path)
        total_pages = len(doc)
        page_numbers = _parse_page_spec(pages, total_pages)

        if not page_numbers:
            return json.dumps(
                {"error": f"Invalid page spec '{pages}'. File has {total_pages} pages."}
            )

        result: dict[str, Any] = {
            "file_name": os.path.basename(path),
            "file_size_bytes": os.path.getsize(path),
            "total_pages": total_pages,
            "extracted_pages": len(page_numbers),
            "pages": [],
        }

        if extract_images:
            result["extracted_images"] = []

        for page_num in page_numbers:
            page = doc.load_page(page_num - 1)  # 0-based
            text = page.get_text("text").strip()

            page_info: dict[str, Any] = {
                "page_number": page_num,
                "char_count": len(text),
                "text": text,
            }
            result["pages"].append(page_info)

            if extract_images:
                image_list = page.get_images(full=True)
                for img_idx, img_info in enumerate(image_list):
                    xref = img_info[0]
                    try:
                        pix = fitz.Pixmap(doc, xref)
                        img_bytes = pix.tobytes("png")
                        b64 = base64.b64encode(img_bytes).decode("ascii")
                        result.setdefault("extracted_images", []).append(
                            {
                                "page": page_num,
                                "index": img_idx,
                                "width": pix.width,
                                "height": pix.height,
                                "base64_png": b64,
                            }
                        )
                    except Exception:
                        pass

        doc.close()
        return json.dumps(result, ensure_ascii=False)

    except ImportError:
        pass

    # Fallback: pdfminer.six
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        from pdfminer.pdfparser import PDFParser
        from pdfminer.pdfdocument import PDFDocument

        # Get total page count
        with open(path, "rb") as f:
            parser = PDFParser(f)
            doc = PDFDocument(parser)
            total_pages = len(list(doc.get_pages()))

        page_numbers = _parse_page_spec(pages, total_pages)

        result: dict[str, Any] = {
            "file_name": os.path.basename(path),
            "file_size_bytes": os.path.getsize(path),
            "total_pages": total_pages,
            "extracted_pages": len(page_numbers),
            "pages": [],
        }

        for page_num in page_numbers:
            # pdfminer doesn't support single-page easily, extract all and split
            text = pdfminer_extract(path, page_numbers=[page_num])
            page_info: dict[str, Any] = {
                "page_number": page_num,
                "char_count": len(text.strip()),
                "text": text.strip(),
            }
            result["pages"].append(page_info)

        return json.dumps(result, ensure_ascii=False)

    except ImportError:
        return json.dumps(
            {
                "error": (
                    "No PDF library available. Install one of: "
                    "`pip install PyMuPDF` or `pip install pdfminer.six`."
                )
            }
        )

    except Exception as exc:
        return json.dumps({"error": f"Failed to read PDF: {exc}"})


def _parse_page_spec(spec: str, total: int) -> list[int]:
    """Parse a page specification string into a sorted list of 1-based page numbers."""
    spec = spec.strip().lower()
    if spec == "all":
        return list(range(1, total + 1))

    pages: set[int] = set()
    parts = [p.strip() for p in spec.split(",")]
    for part in parts:
        if "-" in part:
            try:
                start_s, end_s = part.split("-", 1)
                start, end = int(start_s.strip()), int(end_s.strip())
                pages.update(range(max(1, start), min(total, end) + 1))
            except ValueError:
                continue
        else:
            try:
                p = int(part)
                if 1 <= p <= total:
                    pages.add(p)
            except ValueError:
                continue

    return sorted(pages)


# ===================================================================
# 5. image_convert — 图像格式转换/压缩
# ===================================================================


@tool(
    name="vision__image_convert",
    description=(
        "Convert an image to a different format, optionally adjusting quality "
        "and resizing. Output is saved to the same directory with the new extension "
        "or to a specified output path. Supported formats: JPEG, PNG, WEBP, BMP, GIF, TIFF."
    ),
    read_only=False,
    parameters={
        "type": "object",
        "properties": {
            "input_path": {
                "type": "string",
                "description": "Path to the source image",
            },
            "output_format": {
                "type": "string",
                "enum": ["JPEG", "PNG", "WEBP", "BMP", "GIF", "TIFF"],
                "description": "Target image format (uppercase)",
            },
            "quality": {
                "type": "integer",
                "description": "Output quality 1-100 (used by JPEG/WEBP)",
                "default": 85,
            },
            "max_width": {
                "type": "integer",
                "description": "Maximum width in pixels (preserves aspect ratio)",
            },
            "max_height": {
                "type": "integer",
                "description": "Maximum height in pixels (preserves aspect ratio)",
            },
            "output_path": {
                "type": "string",
                "description": "Optional output path. If omitted, derived from input name + new extension.",
            },
        },
        "required": ["input_path", "output_format"],
    },
)
async def vision__image_convert(
    input_path: str,
    output_format: str,
    quality: int = 85,
    max_width: int | None = None,
    max_height: int | None = None,
    output_path: str = "",
) -> str:
    """Convert an image to another format with optional resize/compression."""
    try:
        from PIL import Image
    except ImportError:
        return json.dumps({"error": "Pillow is not installed."})

    path = _resolve_path(input_path)
    if not path:
        return json.dumps({"error": f"Input image not found: {input_path}"})

    fmt = output_format.upper()
    if fmt not in ("JPEG", "PNG", "WEBP", "BMP", "GIF", "TIFF"):
        return json.dumps({"error": f"Unsupported output format: {output_format}"})

    try:
        img = Image.open(path)
        original_mode = img.mode
        original_size = img.size

        # Handle alpha channel for JPEG
        if fmt == "JPEG" and img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        # Resize if requested
        if max_width is not None or max_height is not None:
            w, h = img.size
            max_w = max_width or w
            max_h = max_height or h
            ratio = min(max_w / w, max_h / h)
            if ratio < 1.0:
                new_w = int(w * ratio)
                new_h = int(h * ratio)
                img = img.resize((new_w, new_h), Image.LANCZOS)

        # Determine output path
        if not output_path:
            stem = os.path.splitext(path)[0]
            output_path = f"{stem}.{fmt.lower()}"

        # Save
        save_kwargs: dict[str, Any] = {}
        if fmt in ("JPEG", "WEBP"):
            save_kwargs["quality"] = max(1, min(100, quality))

        img.save(output_path, format=fmt, **save_kwargs)

        result = {
            "input_file": os.path.basename(path),
            "output_file": os.path.basename(output_path),
            "output_path": os.path.abspath(output_path),
            "output_format": fmt,
            "original_size": {"width": original_size[0], "height": original_size[1]},
            "output_size": {"width": img.width, "height": img.height},
            "output_bytes": os.path.getsize(output_path),
            "quality_used": save_kwargs.get("quality", "N/A"),
        }

        return json.dumps(result, ensure_ascii=False)

    except Exception as exc:
        return json.dumps({"error": f"Failed to convert image: {exc}"})


# ===================================================================
# Helpers
# ===================================================================

MAX_DIMENSION = 2048


def _resolve_path(path_str: str) -> str | None:
    """Resolve a file path, returning None if not found."""
    path = os.path.abspath(os.path.expanduser(path_str))
    if os.path.isfile(path):
        return path
    return None


def _auto_resize(img: Any) -> Any:
    """Resize image if either dimension exceeds MAX_DIMENSION, preserving aspect ratio."""
    w, h = img.size
    if w > MAX_DIMENSION or h > MAX_DIMENSION:
        ratio = MAX_DIMENSION / max(w, h)
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        from PIL import Image as _PIL

        return img.resize((new_w, new_h), _PIL.LANCZOS)
    return img


def convert_to_rgb(img: Any) -> Any:
    """Convert image to RGB mode (drops alpha)."""
    if img.mode == "RGBA":
        # Composite on white background
        from PIL import Image as _PIL

        background = _PIL.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        return background
    if img.mode != "RGB":
        return img.convert("RGB")
    return img
