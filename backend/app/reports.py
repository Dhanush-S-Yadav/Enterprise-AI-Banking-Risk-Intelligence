"""ReportLab PDF reporting of AI analysis with source evidence and limitations."""
import uuid
from html import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, KeepTogether
from . import config, storage

def create_pdf(title,category,analysis,citations,user):
    report_id=str(uuid.uuid4())
    filename=config.REPORT_DIR / f'{report_id}.pdf'
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BankTitle',parent=styles['Title'],fontSize=17,leading=22,textColor=colors.HexColor('#11294a'),spaceAfter=16))
    styles.add(ParagraphStyle(name='BankHeading',parent=styles['Heading2'],textColor=colors.HexColor('#16436f'),spaceBefore=12,spaceAfter=6))
    styles.add(ParagraphStyle(name='BankBody',parent=styles['BodyText'],fontSize=9.5,leading=15,spaceAfter=8))
    doc=SimpleDocTemplate(str(filename),pagesize=A4,rightMargin=2*cm,leftMargin=2*cm,topMargin=2*cm,bottomMargin=2*cm)
    flow=[Paragraph(escape(title),styles['BankTitle']),
          Paragraph(f'<b>Category:</b> {escape(category)}',styles['BankBody']),
          Paragraph(f'<b>Generated UTC:</b> {escape(storage.now())}',styles['BankBody']),
          Paragraph('<b>Dataset:</b> Synthetic banking demonstration documents',styles['BankBody']),
          HRFlowable(width='100%',thickness=1,color=colors.HexColor('#cbd5e1'))]
    flow.append(Paragraph('Executive Summary',styles['BankHeading']))
    # Extractive summary, never fabricated; retain model output and clearly label it.
    intro=' '.join(analysis.split())[:470]
    flow.append(Paragraph(escape(intro or 'No supported summary could be produced.'),styles['BankBody']))
    flow.append(Paragraph('Analysis',styles['BankHeading']))
    for line in analysis.splitlines():
        if not line.strip():continue
        if line.strip().endswith(':') and len(line)<90:flow.append(Paragraph(escape(line.strip()),styles['BankHeading']))
        else:flow.append(Paragraph(escape(line),styles['BankBody']))
    flow.append(Paragraph('Findings',styles['BankHeading']))
    if citations:
        for i,c in enumerate(citations[:6],1):
            flow.append(Paragraph(escape(f'Documented evidence [{i}]: {c["excerpt"][:380]}'),styles['BankBody']))
    else:
        flow.append(Paragraph('No supporting evidence is available. No verified finding is asserted.',styles['BankBody']))
    flow.append(Paragraph('Evidence-Backed Recommendations',styles['BankHeading']))
    raw_lines=[line.strip() for line in analysis.splitlines() if line.strip()]
    recommendation_lines=[]
    for pos,line in enumerate(raw_lines):
        if 'recommend' in line.lower() or 'action:' in line.lower():
            if line.rstrip(':').strip().lower() in ('recommendations','evidence-backed recommendations','recommended actions'):
                recommendation_lines.extend(raw_lines[pos+1:pos+4])
            else: recommendation_lines.append(line)
    if recommendation_lines and citations:
        for line in recommendation_lines[:6]: flow.append(Paragraph(escape(line[:1000]),styles['BankBody']))
    else:
        flow.append(Paragraph('Specific corrective recommendations cannot be established independently from the available passages. Human review is required.',styles['BankBody']))
    flow.append(Paragraph('Evidence & Source References',styles['BankHeading']))
    if citations:
        for i,c in enumerate(citations,1):
            page=f", page {c['page']}" if c.get('page') is not None else ''
            section=f", section {c['section']}" if c.get('section') else ''
            detail=f'[{i}] {c["document_name"]}{page}{section} - {c["excerpt"][:350]}'
            flow.append(Paragraph(escape(detail),styles['BankBody']))
    else:flow.append(Paragraph('No supporting passages were retrieved.',styles['BankBody']))
    flow.append(Paragraph('Limitations and Missing Evidence',styles['BankHeading']))
    flow.append(Paragraph('This output is based solely on user-uploaded or synthetic sample documents. '
                           'It is not regulatory advice, a verified compliance certification, or a live fraud detection result. '
                           'Any claim without complete documentary support must be independently reviewed.',styles['BankBody']))
    def page_footer(canvas,doc_obj):
        canvas.setFont('Helvetica',8)
        canvas.setFillColor(colors.HexColor('#64748b'))
        canvas.drawString(2*cm,1.25*cm,'Enterprise Banking AI | Synthetic academic demonstration')
        canvas.drawRightString(A4[0]-2*cm,1.25*cm,f'Page {doc_obj.page}')
    doc.build(flow,onFirstPage=page_footer,onLaterPages=page_footer)
    record={'id':report_id,'title':title,'category':category,'created_at':storage.now(),
            'created_by':user['id'],'source_documents':list(dict.fromkeys(c['document_id'] for c in citations)),
            'citations':len(citations),'summary':analysis[:500]}
    storage.append('reports.json',record)
    storage.audit('report_generated',user,report_id=report_id,source_documents=record['source_documents'])
    return record
