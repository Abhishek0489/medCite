from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Preformatted, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "installation_guide.md"
OUT = ROOT / "installation_guide.pdf"


def build_styles():
    styles = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "h1",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=8,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#1e293b"),
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=14,
            leftIndent=14,
            firstLineIndent=-8,
            textColor=colors.HexColor("#1e293b"),
        ),
        "code": ParagraphStyle(
            "code",
            parent=styles["Code"],
            fontName="Courier",
            fontSize=9,
            leading=12,
            leftIndent=8,
            rightIndent=8,
            borderColor=colors.HexColor("#cbd5e1"),
            borderWidth=0.6,
            borderPadding=6,
            backColor=colors.HexColor("#f8fafc"),
        ),
    }


def to_paragraph_text(line: str) -> str:
    # Keep this intentionally lightweight; enough for readable PDF output.
    line = (
        line.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return line


def render():
    styles = build_styles()
    md = SRC.read_text(encoding="utf-8")
    lines = md.splitlines()

    story = []
    in_code = False
    code_buf: list[str] = []

    for raw in lines:
        line = raw.rstrip("\n")

        if line.strip().startswith("```"):
            if in_code:
                story.append(Preformatted("\n".join(code_buf), styles["code"]))
                story.append(Spacer(1, 6))
                code_buf = []
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_buf.append(line)
            continue

        if not line.strip():
            story.append(Spacer(1, 6))
            continue

        if line.startswith("# "):
            story.append(Paragraph(to_paragraph_text(line[2:].strip()), styles["h1"]))
            continue

        if line.startswith("## "):
            story.append(Paragraph(to_paragraph_text(line[3:].strip()), styles["h2"]))
            continue

        if line.startswith("- "):
            story.append(
                Paragraph(
                    f"• {to_paragraph_text(line[2:].strip())}",
                    styles["bullet"],
                )
            )
            continue

        story.append(Paragraph(to_paragraph_text(line), styles["body"]))

    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title="MedCite Installation Guide",
    )
    doc.build(story)
    print(f"Wrote styled PDF: {OUT}")


if __name__ == "__main__":
    render()

