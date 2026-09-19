"""Local, in-memory PDF export of the complete generated study notes."""
import io
import re
from html import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak


def build(document, job, section=None):
    output=io.BytesIO()
    styles=getSampleStyleSheet()
    for name in ('Normal','BodyText'):
        styles[name].fontSize=10
        styles[name].leading=15
        styles[name].spaceAfter=7
        styles[name].splitLongWords=True
    styles['Title'].fontSize=23
    styles['Title'].leading=29
    styles['Title'].alignment=TA_LEFT
    story=[]
    def paragraph(text, style='BodyText'):
        text=text.replace('–','-').replace('—','-').replace('\x00','')
        safe=escape(text)
        safe=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',safe)
        safe=re.sub(r'`([^`]+)`',r'\1',safe)
        story.append(Paragraph(safe,styles[style]))
    def markdown(text):
        code=False
        for line in text.splitlines():
            if line.startswith('```'):
                code=not code
                continue
            if not line.strip() or line.strip()=='---': continue
            heading=re.match(r'^(#{1,6})\s+(.+)',line)
            if heading and not code: paragraph(heading[2],'Heading2' if len(heading[1])<3 else 'Heading3')
            else: paragraph(line)
    paragraph('CYBERMENTOR','Heading2')
    paragraph(document['title'],'Title')
    paragraph(section['title'] if section else 'Dossier global','Heading1')
    if section: paragraph(f"Pages du support : {section['first_page']} - {section['last_page']}")
    paragraph('Résumé expliqué et détaillé' if job['kind']=='lesson' else 'Synthèse et notes de lecture','Heading2')
    video=document.get('source_type')=='video'
    paragraph('Support généré localement à vérifier dans la vidéo originale. AUDIO : transcription vocale. ÉCRAN : texte reconnu par OCR sur des captures espacées. Les repères correspondent aux minutes (1 = 00:00 à 00:59). Vérifie les commandes et horodatages ; les affichages brefs et les schémas peuvent être manqués.' if video else 'Support de travail généré localement. Vérifie les points importants dans ton cours original. Les références utilisent les pages du lecteur PDF. Les images et pages sans texte ne sont pas analysées.')
    markdown(job['result']['summary'])
    for part in job['parts']:
        story.append(PageBreak())
        paragraph(f"Bloc de lecture {part['ordinal']+1} - {'repères' if video else 'pages'} {part['first_page']} à {part['last_page']}",'Heading1')
        markdown(part['content'])
    def footer(canvas, doc):
        canvas.saveState();canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#52616b'))
        canvas.drawString(42,25,'CyberMentor | Apprendre, comprendre, pratiquer')
        canvas.drawRightString(A4[0]-42,25,str(doc.page));canvas.restoreState()
    SimpleDocTemplate(output,pagesize=A4,rightMargin=45,leftMargin=45,topMargin=42,bottomMargin=45,title=document['title'],author='CyberMentor').build(story,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()
