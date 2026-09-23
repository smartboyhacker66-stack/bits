import os
import random
import string
import logging
import tempfile

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from pypdf import PdfReader, PdfWriter
import pdfplumber
from gtts import gTTS
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import pikepdf

try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "api77u7y")
FILE_PREFIX = "BlindIndianTechSupport"
SUPPORT_EMAIL = "bits.headquarter505@gmail.com"
SUPPORT_IMAGE_PATH = "support.jpg"

SESSIONS = {}
ADMIN_STATE = {"admin_id": None, "failed_attempts": {}, "logs": []}
SESSION_COUNTER = {"count": 0}


def generate_session_id():
    SESSION_COUNTER["count"] += 1
    random_part = "".join(random.choices(string.ascii_letters + string.digits, k=18))
    return f"{random_part}C#{SESSION_COUNTER['count']}"


def get_session(user_id, username=None):
    if user_id not in SESSIONS:
        SESSIONS[user_id] = {
            "session_id": generate_session_id(),
            "username": username,
            "language": "en",
            "mode": None,
            "files": [],
            "errors": [],
        }
        ADMIN_STATE["logs"].append(
            {
                "session_id": SESSIONS[user_id]["session_id"],
                "user_id": user_id,
                "username": username,
                "actions": [],
                "errors": [],
            }
        )
    return SESSIONS[user_id]

def log_action(user_id, action):
    for entry in ADMIN_STATE["logs"]:
        if entry["user_id"] == user_id:
            entry["actions"].append(action)
            break


def log_error(user_id, error_text):
    for entry in ADMIN_STATE["logs"]:
        if entry["user_id"] == user_id:
            entry["errors"].append(error_text)
            break


LANG_MENU = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("हिंदी", callback_data="lang_hi")],
        [InlineKeyboardButton("मराठी", callback_data="lang_mr")],
        [InlineKeyboardButton("English", callback_data="lang_en")],
    ]
)

CATEGORY_MENU = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("READ", callback_data="cat_read")],
        [InlineKeyboardButton("CREATE", callback_data="cat_create")],
        [InlineKeyboardButton("ORGANISE", callback_data="cat_organise")],
        [InlineKeyboardButton("TRANSFORM", callback_data="cat_transform")],
        [InlineKeyboardButton("ANNOTATE & PROTECT", callback_data="cat_annotate")],
        [InlineKeyboardButton("INSPECT & EXTRACT", callback_data="cat_inspect")],
    ]
)

READ_MENU = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("Read PDF (Send file first)", callback_data="noop")],
    ]
)

CREATE_MENU = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("Images to PDF", callback_data="mode_images_to_pdf")],
        [InlineKeyboardButton("Text to PDF", callback_data="mode_text_to_pdf")],
    ]
)

ORGANISE_MENU = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("Merge PDFs", callback_data="mode_merge")],
        [InlineKeyboardButton("Split PDF", callback_data="mode_split")],
        [InlineKeyboardButton("Cut / Extract Pages", callback_data="mode_extract")],
        [InlineKeyboardButton("Reorder Pages", callback_data="mode_reorder")],
        [InlineKeyboardButton("Delete Pages", callback_data="mode_delete_pages")],
    ]
)

TRANSFORM_MENU = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("PDF to Images", callback_data="mode_pdf_to_images")],
        [InlineKeyboardButton("Compress PDF", callback_data="mode_compress")],
        [InlineKeyboardButton("Resize PDF", callback_data="mode_resize")],
        [InlineKeyboardButton("Rotate Pages", callback_data="mode_rotate")],
    ]
)

ANNOTATE_MENU = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("Add Watermark", callback_data="mode_watermark")],
        [InlineKeyboardButton("Lock PDF", callback_data="mode_lock")],
        [InlineKeyboardButton("Unlock PDF", callback_data="mode_unlock")],
    ]
)

INSPECT_MENU = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("View PDF Metadata", callback_data="mode_metadata")],
    ]
)

SINGLE_FILE_OPS = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("Read (Text)", callback_data="op_read_text")],
        [InlineKeyboardButton("Read (Audio)", callback_data="op_read_audio")],
        [InlineKeyboardButton("Split", callback_data="op_split")],
        [InlineKeyboardButton("Cut / Extract Pages", callback_data="op_extract")],
        [InlineKeyboardButton("Reorder Pages", callback_data="op_reorder")],
        [InlineKeyboardButton("Delete Pages", callback_data="op_delete_pages")],
        [InlineKeyboardButton("PDF to Images", callback_data="op_pdf_to_images")],
        [InlineKeyboardButton("Compress", callback_data="op_compress")],
        [InlineKeyboardButton("Resize", callback_data="op_resize")],
        [InlineKeyboardButton("Rotate Pages", callback_data="op_rotate")],
        [InlineKeyboardButton("Add Watermark", callback_data="op_watermark")],
        [InlineKeyboardButton("Lock PDF", callback_data="op_lock")],
        [InlineKeyboardButton("Unlock PDF", callback_data="op_unlock")],
        [InlineKeyboardButton("View Metadata", callback_data="op_metadata")],
    ]
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    SESSIONS.pop(user.id, None)
    get_session(user.id, user.username)
    await update.message.reply_text(
        "Welcome to Blind Indian Tech Support PDF Manipulation Toolbox\n\n"
        "Please select your preferred language:",
        reply_markup=LANG_MENU,
    )


async def lang_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = get_session(user_id, query.from_user.username)
    lang_code = query.data.replace("lang_", "")
    session["language"] = lang_code
    log_action(user_id, f"language_set:{lang_code}")
    await query.edit_message_text(
        "A full suite of PDF operations — select a category to get started.\n\n"
        "You can also directly send a PDF file to see available operations for it.",
        reply_markup=CATEGORY_MENU,
    )

async def category_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    menus = {
        "cat_read": ("READ", READ_MENU),
        "cat_create": ("CREATE", CREATE_MENU),
        "cat_organise": ("ORGANISE", ORGANISE_MENU),
        "cat_transform": ("TRANSFORM", TRANSFORM_MENU),
        "cat_annotate": ("ANNOTATE & PROTECT", ANNOTATE_MENU),
        "cat_inspect": ("INSPECT & EXTRACT", INSPECT_MENU),
    }
    title, menu = menus[data]
    await query.edit_message_text(f"{title} — select a tool:", reply_markup=menu)


async def mode_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = get_session(user_id, query.from_user.username)
    session["mode"] = query.data.replace("mode_", "")
    session["files"] = []
    log_action(user_id, f"mode_selected:{session['mode']}")

    prompts = {
        "merge": "Send all the PDF files you want to merge, one by one. Type /done when finished.",
        "split": "Send the PDF you want to split into single pages.",
        "extract": "Send the PDF. Then tell me which pages to extract, example: 1-3,5",
        "reorder": "Send the PDF. Then tell me the new page order, example: 3,1,2",
        "delete_pages": "Send the PDF. Then tell me which pages to delete, example: 2,4",
        "pdf_to_images": "Send the PDF to convert its pages into images.",
        "compress": "Send the PDF you want to compress.",
        "resize": "Send the PDF. Then tell me the target page size: A4 or Letter.",
        "rotate": "Send the PDF. Then tell me the rotation: 90, 180 or 270.",
        "watermark": "Send the PDF. Then type the watermark text.",
        "lock": "Send the PDF. Then type the password you want to set.",
        "unlock": "Send the PDF. Then type its current password.",
        "metadata": "Send the PDF to view its metadata.",
        "images_to_pdf": "Send the images (one by one) you want to combine into a PDF. Type /done when finished.",
        "text_to_pdf": "Type or paste the text you want converted into a PDF.",
    }
    await query.edit_message_text(prompts.get(session["mode"], "Send the file."))

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    session = get_session(user.id, user.username)
    mode = session.get("mode")
    doc = update.message.document

    tmp_dir = tempfile.mkdtemp()
    local_path = os.path.join(tmp_dir, doc.file_name)
    tg_file = await doc.get_file()
    await tg_file.download_to_drive(local_path)

    if not doc.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("Please send a PDF file.")
        return

    if mode == "merge":
        session["files"].append(local_path)
        await update.message.reply_text(
            f"'{doc.file_name}' received. Send more files or type /done."
        )
        return

    if not mode:
        session["files"] = [local_path]
        await update.message.reply_text(
            "PDF received. What would you like to do with it?",
            reply_markup=SINGLE_FILE_OPS,
        )
        return

    session["files"] = [local_path]
    await run_single_file_mode(update, context, mode, local_path)

async def op_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = get_session(user_id, query.from_user.username)
    mode = query.data.replace("op_", "")
    session["mode"] = mode
    log_action(user_id, f"op_selected:{mode}")

    if not session["files"]:
        await query.edit_message_text("Please send the PDF file first.")
        return

    local_path = session["files"][0]
    await query.edit_message_text("Processing...")
    await run_single_file_mode(update, context, mode, local_path, query=query)


def extract_text_with_ocr_fallback(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    if text.strip():
        return text
    if OCR_AVAILABLE:
        images = convert_from_path(pdf_path)
        ocr_text = ""
        for img in images:
            ocr_text += pytesseract.image_to_string(img, lang="eng") + "\n"
        return ocr_text
    return ""

def parse_page_ranges(text, max_pages):
    pages = set()
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-")
            for p in range(int(start), int(end) + 1):
                if 1 <= p <= max_pages:
                    pages.add(p)
        elif part.isdigit():
            p = int(part)
            if 1 <= p <= max_pages:
                pages.add(p)
    return sorted(pages)


async def run_single_file_mode(update, context, mode, local_path, query=None):
    user = update.effective_user
    session = get_session(user.id, user.username)
    out_dir = tempfile.mkdtemp()
    chat = update.effective_chat

    try:
        if mode in ("read_text", "text"):
            text = extract_text_with_ocr_fallback(local_path)
            if not text.strip():
                await context.bot.send_message(chat.id, "No readable text found in this PDF.")
                return
            txt_path = os.path.join(out_dir, f"{FILE_PREFIX}_extracted.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text)
            await context.bot.send_document(chat.id, document=open(txt_path, "rb"))

        elif mode == "read_audio":
            text = extract_text_with_ocr_fallback(local_path)
            if not text.strip():
                await context.bot.send_message(chat.id, "No readable text found in this PDF.")
                return
            chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]
            for idx, chunk in enumerate(chunks):
                mp3_path = os.path.join(out_dir, f"{FILE_PREFIX}_audio_{idx+1}.mp3")
                gTTS(text=chunk, lang="en").save(mp3_path)
                await context.bot.send_audio(chat.id, audio=open(mp3_path, "rb"))

        elif mode == "split":
            reader = PdfReader(local_path)
            for i, page in enumerate(reader.pages):
                writer = PdfWriter()
                writer.add_page(page)
                p = os.path.join(out_dir, f"{FILE_PREFIX}_page_{i+1}.pdf")
                with open(p, "wb") as f:
                    writer.write(f)
                await context.bot.send_document(chat.id, document=open(p, "rb"))

        elif mode == "extract":
            session["pending_path"] = local_path
            session["pending_action"] = "extract"
            await context.bot.send_message(chat.id, "Which pages? Example: 1-3,5")

        elif mode == "reorder":
            session["pending_path"] = local_path
            session["pending_action"] = "reorder"
            await context.bot.send_message(chat.id, "New page order? Example: 3,1,2")

        elif mode == "delete_pages":
            session["pending_path"] = local_path
            session["pending_action"] = "delete_pages"
            await context.bot.send_message(chat.id, "Which pages to delete? Example: 2,4")

        elif mode == "pdf_to_images":
            if not OCR_AVAILABLE:
                await context.bot.send_message(chat.id, "PDF to Images feature unavailable on this server.")
                return
            images = convert_from_path(local_path)
            for i, img in enumerate(images):
                p = os.path.join(out_dir, f"{FILE_PREFIX}_page_{i+1}.jpg")
                img.save(p, "JPEG")
                await context.bot.send_document(chat.id, document=open(p, "rb"))

        elif mode == "compress":
            out_path = os.path.join(out_dir, f"{FILE_PREFIX}_compressed.pdf")
            with pikepdf.open(local_path) as pdf:
                pdf.save(out_path, compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
            await context.bot.send_document(chat.id, document=open(out_path, "rb"))

        elif mode == "resize":
            session["pending_path"] = local_path
            session["pending_action"] = "resize"
            await context.bot.send_message(chat.id, "Target page size? Type A4 or Letter")

        elif mode == "rotate":
            session["pending_path"] = local_path
            session["pending_action"] = "rotate"
            await context.bot.send_message(chat.id, "Rotation degrees? Type 90, 180 or 270")

        elif mode == "watermark":
            session["pending_path"] = local_path
            session["pending_action"] = "watermark"
            await context.bot.send_message(chat.id, "Type the watermark text")

        elif mode == "lock":
            session["pending_path"] = local_path
            session["pending_action"] = "lock"
            await context.bot.send_message(chat.id, "Type the password to set")

        elif mode == "unlock":
            session["pending_path"] = local_path
            session["pending_action"] = "unlock"
            await context.bot.send_message(chat.id, "Type the current password")

        elif mode == "metadata":
            reader = PdfReader(local_path)
            meta = reader.metadata
            info = (
                f"Title: {meta.title if meta else 'N/A'}\n"
                f"Author: {meta.author if meta else 'N/A'}\n"
                f"Creator: {meta.creator if meta else 'N/A'}\n"
                f"Pages: {len(reader.pages)}\n"
                f"Encrypted: {reader.is_encrypted}"
            )
            await context.bot.send_message(chat.id, info)

        if session.get("pending_action") is None:
            session["mode"] = None

    except Exception as e:
        logger.exception("Error processing file")
        log_error(user.id, str(e))
        await context.bot.send_message(chat.id, f"An error occurred: {e}")
        session["mode"] = None

async def done_merge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    session = get_session(user.id, user.username)

    if session.get("mode") == "merge":
        if len(session["files"]) < 2:
            await update.message.reply_text("Send at least 2 PDF files before /done.")
            return
        writer = PdfWriter()
        for path in session["files"]:
            reader = PdfReader(path)
            for page in reader.pages:
                writer.add_page(page)
        out_path = os.path.join(tempfile.mkdtemp(), f"{FILE_PREFIX}_merged.pdf")
        with open(out_path, "wb") as f:
            writer.write(f)
        await update.message.reply_document(document=open(out_path, "rb"))
        session["mode"] = None
        session["files"] = []
        return

    if session.get("mode") == "images_to_pdf":
        if not session["files"]:
            await update.message.reply_text("Send at least 1 image before /done.")
            return
        images = [Image.open(p).convert("RGB") for p in session["files"]]
        out_path = os.path.join(tempfile.mkdtemp(), f"{FILE_PREFIX}_images.pdf")
        images[0].save(out_path, save_all=True, append_images=images[1:])
        await update.message.reply_document(document=open(out_path, "rb"))
        session["mode"] = None
        session["files"] = []
        return

    await update.message.reply_text("Nothing to finish right now.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    session = get_session(user.id, user.username)
    if session.get("mode") != "images_to_pdf":
        await update.message.reply_text("Please select 'Images to PDF' from the menu first.")
        return
    photo = update.message.photo[-1]
    tg_file = await photo.get_file()
    tmp_dir = tempfile.mkdtemp()
    local_path = os.path.join(tmp_dir, f"{len(session['files'])+1}.jpg")
    await tg_file.download_to_drive(local_path)
    session["files"].append(local_path)
    await update.message.reply_text("Image received. Send more or type /done.")


async def handle_text_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    session = get_session(user.id, user.username)
    text = update.message.text.strip()

    if session.get("mode") == "text_to_pdf":
        out_path = os.path.join(tempfile.mkdtemp(), f"{FILE_PREFIX}_text.pdf")
        c = canvas.Canvas(out_path, pagesize=letter)
        width, height = letter
        y = height - 50
        for line in text.split("\n"):
            c.drawString(50, y, line[:100])
            y -= 15
            if y < 50:
                c.showPage()
                y = height - 50
        c.save()
        await update.message.reply_document(document=open(out_path, "rb"))
        session["mode"] = None
        return

    if "admin_step" in session:
        await handle_admin_flow(update, context, text)
        return

    pending = session.get("pending_action")
    if not pending:
        await update.message.reply_text("Please use /start to see the menu.")
        return

    path = session.pop("pending_path")
    session.pop("pending_action", None)
    out_dir = tempfile.mkdtemp()

    try:
        if pending == "extract":
            reader = PdfReader(path)
            pages = parse_page_ranges(text, len(reader.pages))
            writer = PdfWriter()
            for p in pages:
                writer.add_page(reader.pages[p - 1])
            out_path = os.path.join(out_dir, f"{FILE_PREFIX}_extracted.pdf")
            with open(out_path, "wb") as f:
                writer.write(f)
            await update.message.reply_document(document=open(out_path, "rb"))

        elif pending == "reorder":
            reader = PdfReader(path)
            order = [int(x.strip()) for x in text.split(",")]
            writer = PdfWriter()
            for p in order:
                writer.add_page(reader.pages[p - 1])
            out_path = os.path.join(out_dir, f"{FILE_PREFIX}_reordered.pdf")
            with open(out_path, "wb") as f:
                writer.write(f)
            await update.message.reply_document(document=open(out_path, "rb"))

        elif pending == "delete_pages":
            reader = PdfReader(path)
            to_delete = set(int(x.strip()) for x in text.split(","))
            writer = PdfWriter()
            for i, page in enumerate(reader.pages):
                if (i + 1) not in to_delete:
                    writer.add_page(page)
            out_path = os.path.join(out_dir, f"{FILE_PREFIX}_deleted_pages.pdf")
            with open(out_path, "wb") as f:
                writer.write(f)
            await update.message.reply_document(document=open(out_path, "rb"))

        elif pending == "resize":
            from reportlab.lib.pagesizes import A4, LETTER
            target = A4 if text.upper() == "A4" else LETTER
            reader = PdfReader(path)
            writer = PdfWriter()
            for page in reader.pages:
                page.scale_to(target[0], target[1])
                writer.add_page(page)
            out_path = os.path.join(out_dir, f"{FILE_PREFIX}_resized.pdf")
            with open(out_path, "wb") as f:
                writer.write(f)
            await update.message.reply_document(document=open(out_path, "rb"))

        elif pending == "rotate":
            reader = PdfReader(path)
            writer = PdfWriter()
            for page in reader.pages:
                page.rotate(int(text))
                writer.add_page(page)
            out_path = os.path.join(out_dir, f"{FILE_PREFIX}_rotated.pdf")
            with open(out_path, "wb") as f:
                writer.write(f)
            await update.message.reply_document(document=open(out_path, "rb"))

        elif pending == "watermark":
            wm_path = os.path.join(out_dir, "wm.pdf")
            c = canvas.Canvas(wm_path, pagesize=letter)
            c.setFont("Helvetica", 40)
            c.setFillGray(0.5, 0.3)
            c.saveState()
            c.translate(300, 400)
            c.rotate(45)
            c.drawCentredString(0, 0, text)
            c.restoreState()
            c.save()
            wm_page = PdfReader(wm_path).pages[0]
            reader = PdfReader(path)
            writer = PdfWriter()
            for page in reader.pages:
                page.merge_page(wm_page)
                writer.add_page(page)
            out_path = os.path.join(out_dir, f"{FILE_PREFIX}_watermarked.pdf")
            with open(out_path, "wb") as f:
                writer.write(f)
            await update.message.reply_document(document=open(out_path, "rb"))

        elif pending == "lock":
            reader = PdfReader(path)
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            writer.encrypt(text)
            out_path = os.path.join(out_dir, f"{FILE_PREFIX}_locked.pdf")
            with open(out_path, "wb") as f:
                writer.write(f)
            await update.message.reply_document(document=open(out_path, "rb"))

        elif pending == "unlock":
            reader = PdfReader(path)
            if reader.is_encrypted:
                reader.decrypt(text)
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            out_path = os.path.join(out_dir, f"{FILE_PREFIX}_unlocked.pdf")
            with open(out_path, "wb") as f:
                writer.write(f)
            await update.message.reply_document(document=open(out_path, "rb"))

        session["mode"] = None

    except Exception as e:
        logger.exception("Error in text reply handler")
        log_error(user.id, str(e))
        await update.message.reply_text(f"An error occurred: {e}")
        session["mode"] = None

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = f"For any queries you can reach out to us: {SUPPORT_EMAIL}"
    try:
        await update.message.reply_photo(photo=open(SUPPORT_IMAGE_PATH, "rb"), caption=caption)
    except Exception:
        await update.message.reply_text(caption)


async def admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    session = get_session(user.id, user.username)

    if ADMIN_STATE["failed_attempts"].get(user.id, 0) >= 3:
        await update.message.reply_text("Too many failed attempts. Access temporarily blocked.")
        return

    if ADMIN_STATE["admin_id"] is not None and user.id != ADMIN_STATE["admin_id"]:
        await update.message.reply_text("Access denied.")
        return

    session["admin_step"] = "awaiting_password"
    await update.message.reply_text("Enter admin password:")

async def handle_admin_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    user = update.effective_user
    session = get_session(user.id, user.username)
    session.pop("admin_step", None)

    if text != ADMIN_PASSWORD:
        ADMIN_STATE["failed_attempts"][user.id] = ADMIN_STATE["failed_attempts"].get(user.id, 0) + 1
        if ADMIN_STATE["admin_id"] is not None:
            try:
                await context.bot.send_message(
                    ADMIN_STATE["admin_id"],
                    f"Warning: someone attempted to access the admin panel with a wrong password. User ID: {user.id}",
                )
            except Exception:
                pass
        await update.message.reply_text("Incorrect password.")
        return

    if ADMIN_STATE["admin_id"] is None:
        ADMIN_STATE["admin_id"] = user.id

    if user.id != ADMIN_STATE["admin_id"]:
        await update.message.reply_text("Access denied.")
        return

    ADMIN_STATE["failed_attempts"][user.id] = 0
    lines = ["Admin Panel — Recent Sessions:\n"]
    for entry in ADMIN_STATE["logs"][-20:]:
        lines.append(
            f"Session: {entry['session_id']} | User: {entry['username']} | "
            f"Actions: {entry['actions']} | Errors: {entry['errors']}"
        )
    await update.message.reply_text("\n".join(lines) if len(lines) > 1 else "No sessions logged yet.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("done", done_merge))
    app.add_handler(CommandHandler("support", support))
    app.add_handler(CommandHandler("admin", admin_entry))
    app.add_handler(CallbackQueryHandler(lang_choice, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(category_choice, pattern="^cat_"))
    app.add_handler(CallbackQueryHandler(mode_choice, pattern="^mode_"))
    app.add_handler(CallbackQueryHandler(op_choice, pattern="^op_"))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_reply))

    logger.info("Bot started, polling...")
    app.run_polling()

if __name__ == "__main__":
    main()          
