"""Generate styled PDF report using ReportLab"""
import io
import datetime
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm, inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image

# Professional Light Mode Colors
PRIMARY_BLUE = colors.HexColor('#0F172A')     # Dark Slate/Navy for headers
ACCENT_BLUE = colors.HexColor('#2563EB')      # ExamAI blue
SUCCESS_GREEN = colors.HexColor('#059669')
WARNING_AMBER = colors.HexColor('#D97706')
DANGER_RED = colors.HexColor('#DC2626')
TEXT_PRIMARY = colors.HexColor('#1E293B')
TEXT_SECONDARY = colors.HexColor('#64748B')
BG_LIGHT = colors.HexColor('#F8FAFC')
BORDER_COLOR = colors.HexColor('#E2E8F0')
WHITE = colors.white

def grade_color(pct):
    if pct >= 80: return SUCCESS_GREEN
    if pct >= 60: return ACCENT_BLUE
    if pct >= 40: return WARNING_AMBER
    return DANGER_RED

def letter_grade(pct):
    if pct >= 90: return 'A+'
    if pct >= 80: return 'A'
    if pct >= 70: return 'B'
    if pct >= 60: return 'C'
    if pct >= 50: return 'D'
    return 'F'

def safe_text(text):
    if not text:
        return ""
    return escape(str(text)).replace('\n', '<br/>')

def generate_report(submission, exam, student_name, narrative=''):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            leftMargin=1.5*cm, rightMargin=1.5*cm)
    story = []
    
    # Do not mutate global stylesheets or you'll throw KeyError! Keep them standalone.
    title_style = ParagraphStyle(name='ReportTitle', fontName='Helvetica-Bold', fontSize=24, textColor=PRIMARY_BLUE)
    subtitle_style = ParagraphStyle(name='ReportSubtitle', fontName='Helvetica', fontSize=10, textColor=TEXT_SECONDARY)
    section_title_style = ParagraphStyle(name='ReportSectionTitle', fontName='Helvetica-Bold', fontSize=14, textColor=PRIMARY_BLUE, spaceBefore=12, spaceAfter=6)
    normal_text_style = ParagraphStyle(name='ReportNormalText', fontName='Helvetica', fontSize=10, textColor=TEXT_PRIMARY, leading=14)
    italic_text_style = ParagraphStyle(name='ReportItalicText', fontName='Helvetica-Oblique', fontSize=9, textColor=TEXT_SECONDARY, leading=12)
    
    pct = submission.get('percentage', 0)
    grade = letter_grade(pct)
    gc = grade_color(pct)
    
    # 1. Header
    date_str = datetime.datetime.now().strftime("%B %d, %Y")
    hdr_table = Table([
        [Paragraph('<b>ExamAI</b>', title_style), 
         Paragraph(f'<b>OFFICIAL EVALUATION REPORT</b><br/>{date_str}', ParagraphStyle('hdr_right', fontName='Helvetica-Bold', fontSize=9, textColor=TEXT_SECONDARY, alignment=2))]
    ], colWidths=[10*cm, 8*cm])
    hdr_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10)
    ]))
    story.append(hdr_table)
    story.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY_BLUE, spaceAfter=15))

    # 2. Student & Exam Info
    info_table = Table([
        [Paragraph('<font color="#64748B" size="8">STUDENT NAME</font><br/><b>{}</b>'.format(safe_text(student_name)), normal_text_style),
         Paragraph('<font color="#64748B" size="8">EXAM TITLE</font><br/><b>{}</b>'.format(safe_text(exam.get("title", "N/A"))), normal_text_style),
         Paragraph('<font color="#64748B" size="8">SUBMISSION ID</font><br/><b>{}</b>'.format(safe_text(submission.get('id', 'N/A')[:8].upper() if submission.get('id') else 'N/A')), normal_text_style)]
    ], colWidths=[6.5*cm, 7.5*cm, 4*cm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT),
        ('PADDING', (0,0), (-1,-1), 10),
        ('BOX', (0,0), (-1,-1), 1, BORDER_COLOR)
    ]))
    story.append(info_table)
    story.append(Spacer(1, 15))

    # 3. Score Summary
    total = submission.get('totalScore', 0)
    maxs = submission.get('maxScore', 0)
    passed_str = 'PASS' if pct >= 50 else 'FAIL'
    pass_color = SUCCESS_GREEN if pct >= 50 else DANGER_RED
    
    score_table = Table([
        [
            Paragraph('<font color="#64748B" size="10">TOTAL SCORE</font>', ParagraphStyle('st1', alignment=1)),
            Paragraph('<font color="#64748B" size="10">PERCENTAGE</font>', ParagraphStyle('st2', alignment=1)),
            Paragraph('<font color="#64748B" size="10">FINAL GRADE</font>', ParagraphStyle('st3', alignment=1)),
            Paragraph('<font color="#64748B" size="10">STATUS</font>', ParagraphStyle('st4', alignment=1))
        ],
        [
            Paragraph(f'<font color="#1E293B" size="18"><b>{total} / {maxs}</b></font>', ParagraphStyle('sv1', alignment=1)),
            Paragraph(f'<font color="{gc.hexval()}" size="18"><b>{pct}%</b></font>', ParagraphStyle('sv2', alignment=1)),
            Paragraph(f'<font color="{gc.hexval()}" size="18"><b>{grade}</b></font>', ParagraphStyle('sv3', alignment=1)),
            Paragraph(f'<font color="{pass_color.hexval()}" size="18"><b>{passed_str}</b></font>', ParagraphStyle('sv4', alignment=1))
        ]
    ], colWidths=[4.5*cm, 4.5*cm, 4.5*cm, 4.5*cm])
    
    score_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 2),
        ('TOPPADDING', (0,1), (-1,1), 2),
        ('BOTTOMPADDING', (0,1), (-1,1), 10),
        ('LINEAFTER', (0,0), (2,1), 1, BORDER_COLOR)
    ]))
    story.append(score_table)
    story.append(Spacer(1, 20))

    # 4. Narrative / Executive Summary
    if narrative:
        story.append(Paragraph('EXECUTIVE SUMMARY', section_title_style))
        narrative_box = Table([[Paragraph(safe_text(narrative), normal_text_style)]], colWidths=[18*cm])
        narrative_box.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
            ('PADDING', (0,0), (-1,-1), 12),
            ('LEFTPADDING', (0,0), (-1,-1), 15),
            ('LINELEFT', (0,0), (-1,-1), 3, ACCENT_BLUE)
        ]))
        story.append(narrative_box)
        story.append(Spacer(1, 15))

    # 5. Detailed Breakdown
    story.append(Paragraph('DETAILED BREAKDOWN', section_title_style))
    
    grades_data = submission.get('grades', [])
    questions_map = {str(q.get('number', '?')): q for q in exam.get('questions', [])}
    
    for idx, g in enumerate(grades_data):
        qnum = str(g.get('questionNumber', '?'))
        # Using string matching to be safe
        qobj = questions_map.get(qnum, {})
        qpct = g.get('percentage', 0)
        qmarks = g.get("marks", 0)
        qmax = g.get("maxMarks", 0)
        
        qtext = qobj.get("text", "Question Text Not Found")
        if len(qtext) > 200:
            qtext = qtext[:197] + "..."
            
        # Question Header
        qhead_table = Table([
            [Paragraph(f'<b>Q{escape(qnum)}</b>', ParagraphStyle('qnh', fontName='Helvetica-Bold', fontSize=11, textColor=WHITE)),
             Paragraph(f'<font color="white"><b>{qmarks} / {qmax}</b> Marks</font>', ParagraphStyle('qsh', fontName='Helvetica-Bold', fontSize=11, textColor=WHITE, alignment=2))]
        ], colWidths=[12*cm, 6*cm])
        qhead_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), PRIMARY_BLUE),
            ('PADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
        ]))
        story.append(qhead_table)
        
        # Details directly to story
        story.append(Spacer(1, 10))
        story.append(Paragraph(f'<font color="#64748B"><b>Question:</b></font> {safe_text(qtext)}', normal_text_style))
        story.append(Spacer(1, 8))
        
        if g.get('studentAnswer'):
            story.append(Paragraph(f'<font color="#1E293B"><b>Student Answer:</b></font> {safe_text(g["studentAnswer"])}', normal_text_style))
            story.append(Spacer(1, 8))
            
        if g.get('feedback'):
            story.append(Paragraph(f'<font color="#2563EB"><b>AI Feedback:</b></font> {safe_text(g["feedback"])}', normal_text_style))
            story.append(Spacer(1, 8))
            
        imps = g.get('improvements', [])
        if imps:
            # Join improvements with bullets
            bulls = "<br/>".join([f"• {safe_text(imp)}" for imp in imps])
            story.append(Paragraph(f'<font color="#D97706"><b>Areas for Improvement:</b></font><br/>{bulls}', ParagraphStyle('imp', fontName='Helvetica', fontSize=9, textColor=TEXT_PRIMARY, leading=12)))
            story.append(Spacer(1, 8))
            
        # ML metrics in small gray text
        bd = g.get('breakdown', {})
        if bd:
            bd_txt = ' | '.join([f'{k.upper()}: {v}%' for k,v in bd.items()])
            story.append(Paragraph(f'ML Confidence Score: {bd_txt}', italic_text_style))
            
        story.append(Spacer(1, 15))
        story.append(HRFlowable(width='100%', thickness=1, color=BORDER_COLOR))
        story.append(Spacer(1, 15))

    # 6. Footer
    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(TEXT_SECONDARY)
        canvas.drawCentredString(A4[0] / 2.0, 1*cm, f"ExamAI • ML-powered Exam Evaluation • Page {doc.page}")
        canvas.restoreState()
        
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    return buf.getvalue()
