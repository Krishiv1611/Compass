"""Build the Compass product and technical report."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / "Compass_Product_and_Technical_Report.docx"
ASSETS = ROOT / "artifacts" / "compass_report_assets"
REPORT_TRUTH_CLAIMS = {
    "workflow": (
        "Compaction is entered only when messages exceed context.summarize_after "
        "(default 10) and no tool calls are pending."
    ),
    "refresh": (
        "Access tokens stay in browser memory; rotating, single-use refresh tokens "
        "use an HttpOnly cookie scoped to /api/auth, and refresh generation advances "
        "before the next token is issued."
    ),
}
BLUE,NAVY,INK,MUTED,CORAL,GREEN,AMBER,LINE = "2864DC","172B4D","172027","596773","E0604E","2E8B62","B7791F","CBD5E1"
LIGHT_BLUE,LIGHT_GRAY,WHITE = "E8EEF8","F2F4F7","FFFFFF"

def pc(color): return color if color.startswith("#") else "#" + color


def img_font(size, bold=False):
    p = Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf")
    return ImageFont.truetype(str(p), size) if p.exists() else ImageFont.load_default()


def centered(draw, box, text, size=25, color=INK):
    x,y,w,h=box; f=img_font(size, True)
    b=draw.multiline_textbbox((0,0), text, font=f, align="center", spacing=4)
    tw,th=b[2]-b[0],b[3]-b[1]
    draw.multiline_text((x+(w-tw)/2,y+(h-th)/2),text,font=f,fill=pc(color),align="center",spacing=4)


def dibox(draw,x,y,w,h,text,fill=LIGHT_BLUE,outline=BLUE,size=25):
    draw.rounded_rectangle((x,y,x+w,y+h),16,fill=pc(fill),outline=pc(outline),width=3)
    centered(draw,(x,y,w,h),text,size,NAVY)


def arrow(draw,start,end,color=BLUE):
    draw.line((start,end),fill=pc(color),width=5); x0,y0=start; x1,y1=end
    if abs(x1-x0)>abs(y1-y0):
        d=1 if x1>x0 else -1; pts=[(x1,y1),(x1-18*d,y1-9),(x1-18*d,y1+9)]
    else:
        d=1 if y1>y0 else -1; pts=[(x1,y1),(x1-9,y1-18*d),(x1+9,y1-18*d)]
    draw.polygon(pts,fill=pc(color))


def make_architecture():
    ASSETS.mkdir(parents=True,exist_ok=True); path=ASSETS/"architecture.png"
    im=Image.new("RGB",(1500,900),pc(WHITE)); d=ImageDraw.Draw(im)
    d.text((60,30),"Compass system architecture",font=img_font(38,True),fill=pc(NAVY))
    d.text((60,80),"Two interfaces, one governed agent workflow",font=img_font(22),fill=pc(MUTED))
    dibox(d,70,180,290,115,"Terminal UI\nlocal repository")
    dibox(d,70,420,290,115,"React workbench\nisolated workspace")
    dibox(d,500,415,320,125,"FastAPI API\nREST + WebSocket",LIGHT_GRAY,LINE)
    dibox(d,970,280,360,160,"LangGraph agent\nplanning, execution,\nsafety, validation",LIGHT_BLUE,CORAL,28)
    dibox(d,500,660,300,105,"PostgreSQL\nsessions, runs, patches",LIGHT_GRAY,LINE,23)
    dibox(d,900,660,300,105,"Workspace storage\nper-user project files",LIGHT_GRAY,LINE,23)
    dibox(d,1225,545,200,105,"GitHub\nconnection","FFF3EE",CORAL,22)
    dibox(d,1000,100,300,90,"LLM providers\nmodels + embeddings",LIGHT_GRAY,LINE,21)
    for a,b,c in [((360,238),(970,345),BLUE),((360,478),(500,478),BLUE),((820,478),(970,405),BLUE),((650,540),(650,660),BLUE),((770,540),(1010,660),BLUE),((820,500),(1225,595),CORAL),((1150,280),(1150,190),CORAL)]: arrow(d,a,b,c)
    d.text((690,815),"Tools, skills, optional retrieval and local MCP stay inside surface-specific policy boundaries.",font=img_font(18),fill=pc(MUTED))
    im.save(path); return path


def make_workflow():
    from tools.render_workflow import describe_builder

    ASSETS.mkdir(parents=True,exist_ok=True); path=ASSETS/"workflow.png"
    im=Image.new("RGB",(1500,1050),pc(WHITE)); d=ImageDraw.Draw(im)
    descriptor=describe_builder()
    registered=set(descriptor.nodes)-{"__start__","__end__"}
    groups=[
        ("Entry + context",["direct_chat","context_injector"],LIGHT_GRAY,LINE),
        ("Planning + skills",["planner","plan_approval","clarifier","skill_manager"],"FFF3EE",CORAL),
        ("Read-only analysis",["coordinator","synthesis"],"EAF7EF",GREEN),
        ("Single executor spine",["executor","check_safety","tools"],LIGHT_BLUE,BLUE),
        ("Validation + recovery",["linter_node","evaluator","summary_node","loop_recovery","goal_limit","loop_limit"],"FFF7E8",AMBER),
        ("Verification",["verification_hooks","verification_hooks_finalize"],"EAF7EF",GREEN),
    ]
    assigned={node for _title,nodes,_fill,_outline in groups for node in nodes}
    if registered-assigned:
        groups.append(("Other registered nodes",sorted(registered-assigned),LIGHT_GRAY,LINE))
    d.text((60,30),"Registered Compass workflow",font=img_font(38,True),fill=pc(NAVY))
    d.text((60,80),"All current StateGraph nodes, grouped for readability; exact edges live in the generated workflow document.",font=img_font(20),fill=pc(MUTED))
    positions=[(60,165),(540,165),(1020,165),(60,535),(540,535),(1020,535),(540,820)]
    for (title,nodes,fill,outline),(x,y) in zip(groups,positions):
        visible=[node for node in nodes if node in registered]
        label=title+"\n\n"+"\n".join(visible)
        dibox(d,x,y,420,300 if y<800 else 145,label,fill,outline,22)
    d.text((60,920),f"Descriptor: {len(registered)} runtime nodes · {len(descriptor.edges)} statically registered destinations · {len(descriptor.dynamic_routes)} runtime-selected routers",font=img_font(18),fill=pc(MUTED))
    d.text((60,965),"Plan/tool/clarification interrupts are explicit. Read-only workers return evidence to the executor; they do not mutate files.",font=img_font(18),fill=pc(MUTED))
    im.save(path); return path


def set_font(run,size=11,color=INK,bold=False,italic=False):
    run.font.name="Calibri"; run._element.rPr.rFonts.set(qn("w:ascii"),"Calibri"); run._element.rPr.rFonts.set(qn("w:hAnsi"),"Calibri")
    run.font.size=Pt(size); run.font.color.rgb=RGBColor.from_string(color); run.bold=bold; run.italic=italic


def shade(cell,fill):
    pr=cell._tc.get_or_add_tcPr(); shd=pr.find(qn("w:shd"))
    if shd is None: shd=OxmlElement("w:shd"); pr.append(shd)
    shd.set(qn("w:fill"),fill)


def table_geometry(table,widths):
    table.autofit=False; pr=table._tbl.tblPr
    tw=pr.first_child_found_in("w:tblW")
    if tw is None: tw=OxmlElement("w:tblW")
    if tw.getparent() is None: pr.append(tw)
    tw.set(qn("w:w"),str(sum(widths))); tw.set(qn("w:type"),"dxa")
    ind=pr.first_child_found_in("w:tblInd")
    if ind is None: ind=OxmlElement("w:tblInd")
    if ind.getparent() is None: pr.append(ind)
    ind.set(qn("w:w"),"120"); ind.set(qn("w:type"),"dxa")
    for col,w in zip(table._tbl.tblGrid.gridCol_lst,widths): col.set(qn("w:w"),str(w))
    for row in table.rows:
        for cell,w in zip(row.cells,widths):
            cp=cell._tc.get_or_add_tcPr(); cw=cp.find(qn("w:tcW"))
            if cw is None: cw=OxmlElement("w:tcW")
            if cw.getparent() is None: cp.append(cw)
            cw.set(qn("w:w"),str(w)); cw.set(qn("w:type"),"dxa"); cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            mar=cp.first_child_found_in("w:tcMar")
            if mar is None: mar=OxmlElement("w:tcMar")
            if mar.getparent() is None: cp.append(mar)
            for name,val in (("top",80),("start",120),("bottom",80),("end",120)):
                node=mar.find(qn("w:"+name))
                if node is None: node=OxmlElement("w:"+name)
                if node.getparent() is None: mar.append(node)
                node.set(qn("w:w"),str(val)); node.set(qn("w:type"),"dxa")


def configure(doc):
    sec=doc.sections[0]; sec.top_margin=sec.bottom_margin=sec.left_margin=sec.right_margin=Inches(1); sec.header_distance=sec.footer_distance=Inches(.492)
    normal=doc.styles["Normal"]; normal.font.name="Calibri"; normal.font.size=Pt(11); normal.font.color.rgb=RGBColor.from_string(INK); normal.paragraph_format.space_after=Pt(6); normal.paragraph_format.line_spacing=1.1
    for name,size,color,before,after in [("Heading 1",16,BLUE,16,8),("Heading 2",13,BLUE,12,6),("Heading 3",12,NAVY,8,4)]:
        s=doc.styles[name]; s.font.name="Calibri"; s.font.size=Pt(size); s.font.color.rgb=RGBColor.from_string(color); s.font.bold=True; s.paragraph_format.space_before=Pt(before); s.paragraph_format.space_after=Pt(after)
    cap=doc.styles["Caption"]; cap.font.name="Calibri"; cap.font.size=Pt(9); cap.font.italic=True; cap.font.color.rgb=RGBColor.from_string(MUTED); cap.paragraph_format.space_after=Pt(10)
    hp=sec.header.paragraphs[0]; set_font(hp.add_run("COMPASS  |  PRODUCT AND TECHNICAL REPORT"),8,MUTED,True)
    fp=sec.footer.paragraphs[0]; fp.alignment=WD_ALIGN_PARAGRAPH.RIGHT; set_font(fp.add_run("Compass - July 2026  |  "),8,MUTED)
    fld=OxmlElement("w:fldSimple"); fld.set(qn("w:instr"),"PAGE"); fp._p.append(fld)


def para(doc,text="",style=None,size=11,color=INK,bold=False,italic=False):
    p=doc.add_paragraph(style=style); set_font(p.add_run(text),size,color,bold,italic); return p


def bullets(doc,items):
    for item in items:
        p=doc.add_paragraph(style="List Bullet"); p.paragraph_format.space_after=Pt(4); p.paragraph_format.line_spacing=1.15; set_font(p.add_run(item))


def table(doc,headers,rows,widths):
    t=doc.add_table(rows=1,cols=len(headers)); t.style="Table Grid"; table_geometry(t,widths)
    for c,text in zip(t.rows[0].cells,headers): shade(c,LIGHT_BLUE); c.paragraphs[0].paragraph_format.space_after=Pt(0); set_font(c.paragraphs[0].add_run(text),10,NAVY,True)
    trpr=t.rows[0]._tr.get_or_add_trPr(); repeat=OxmlElement("w:tblHeader"); repeat.set(qn("w:val"),"true"); trpr.append(repeat)
    for vals in rows:
        cells=t.add_row().cells
        for i,(c,text) in enumerate(zip(cells,vals)):
            if i==0: shade(c,LIGHT_GRAY)
            c.paragraphs[0].paragraph_format.space_after=Pt(0); set_font(c.paragraphs[0].add_run(text),9 if len(text)>100 else 10,INK,i==0)
    table_geometry(t,widths); doc.add_paragraph().paragraph_format.space_after=Pt(2); return t


def callout(doc,title,text):
    p=doc.add_paragraph(); p.paragraph_format.space_before=Pt(4); p.paragraph_format.space_after=Pt(8); p.paragraph_format.left_indent=Inches(.14); p.paragraph_format.right_indent=Inches(.14)
    ppr=p._p.get_or_add_pPr(); shd=OxmlElement("w:shd"); shd.set(qn("w:fill"),"F4F6F9"); ppr.append(shd)
    borders=OxmlElement("w:pBdr"); left=OxmlElement("w:left"); left.set(qn("w:val"),"single"); left.set(qn("w:sz"),"18"); left.set(qn("w:space"),"6"); left.set(qn("w:color"),BLUE); borders.append(left); ppr.append(borders)
    set_font(p.add_run(title+"\n"),10,BLUE,True); set_font(p.add_run(text),10)


def section_title(doc,title): doc.add_heading(title,level=1)


def build():
    arch,flow=make_architecture(),make_workflow(); doc=Document(); configure(doc)
    p=doc.add_paragraph(); p.paragraph_format.space_before=Pt(60); p.paragraph_format.space_after=Pt(8); set_font(p.add_run("PRODUCT AND TECHNICAL REPORT"),11,CORAL,True)
    p=doc.add_paragraph(); p.paragraph_format.space_after=Pt(9); set_font(p.add_run("Compass"),34,NAVY,True)
    p=doc.add_paragraph(); p.paragraph_format.space_after=Pt(24); set_font(p.add_run("An inspectable AI coding workbench for project change, review, and delivery"),15,MUTED)
    callout(doc,"EXECUTIVE SUMMARY","Compass combines a governed LangGraph agent with a local terminal UI and an authenticated web workbench. It helps developers move from project understanding to reviewed changes and GitHub delivery while keeping context, approvals, and run activity visible.")
    p=doc.add_paragraph(); p.paragraph_format.space_before=Pt(18); set_font(p.add_run("Prepared from the current Compass implementation\n21 August 2026"),10,MUTED)
    doc.add_page_break()

    section_title(doc,"1. Product overview")
    para(doc,"Compass is a coding assistant designed as a workbench rather than a chat box. It provides a structured route from a developer request to project context, an execution plan, approved tool actions, patch review, and a publishable GitHub outcome.")
    bullets(doc,["Local-first terminal workflow for developers working directly in a checked-out repository.","Authenticated browser workspace for isolated uploads and GitHub imports.","Explicit controls for context, interaction mode, patches, approvals, activity, and publishing.","One agent workflow shared across interfaces, with different safety boundaries for local and hosted execution."])
    callout(doc,"PRODUCT POSITION","Compass differentiates itself through clarity and control: it makes powerful agent behavior understandable without exposing raw internal reasoning or hiding project-changing operations.")

    section_title(doc,"2. System architecture")
    para(doc,"The terminal UI operates on a local repository. The web workbench talks to FastAPI, which owns authentication, sessions, isolated workspaces, runs, patches and GitHub connections. Both use the LangGraph agent workflow.")
    doc.add_picture(str(arch),width=Inches(6.45)); doc.inline_shapes[-1]._inline.docPr.set("descr","Compass system architecture connecting the terminal UI and React workbench to FastAPI, LangGraph, PostgreSQL, workspace storage, GitHub and model providers."); p=para(doc,"Figure 1. Compass joins local and web experiences through one governed agent workflow.","Caption"); p.alignment=WD_ALIGN_PARAGRAPH.CENTER

    section_title(doc,"3. Feature set")
    table(doc,["Capability","What it enables","Surface"],[
        ["Project workbench","Files, editor, changes, preview, agent and activity views share one responsive workspace state.","Web"],
        ["Agent execution","Ask, Edit, Plan and Goal modes route through one executor spine with typed interrupts, tools, recovery and evaluation.","TUI + web"],
        ["Context intelligence","File search and pinned context work directly; semantic retrieval and memory require embedding configuration and credentials.","Agent + workbench"],
        ["Review and recovery","Patch counts, diff review, accept/reject, undo, run stages, failure details and loop recovery.","TUI + web"],
        ["GitHub delivery","Separate repository connection, import, branch creation, commits and draft pull requests.","Web + TUI helpers"],
        ["Local integrations","Local MCP configuration, custom tools, skills, shell execution and repository configuration.","TUI only"],
    ],[2100,5000,2260])

    section_title(doc,"4. Technology stack")
    table(doc,["Layer","Primary technologies","Role"],[
        ["Frontend","React 19, TypeScript, Vite, Tailwind CSS, Base UI, CodeMirror, WebContainers","Responsive workbench, editor, diff, preview and accessible controls."],
        ["Backend","FastAPI, Pydantic, SQLAlchemy, Alembic, Uvicorn","Authenticated REST/WebSocket API and product services."],
        ["Agent","LangGraph, LangChain, provider adapters","Planning, models, tools, recovery and persistent routing."],
        ["Persistence","PostgreSQL, psycopg, LangGraph Postgres checkpointing","Users, sessions, messages, runs, patches, workspaces and resumable state."],
        ["Intelligence","RAG indexing, chunking, retrieval, embeddings","Relevant project evidence and semantic source search."],
        ["Safety + operations","Typed interrupts, tool policy, JWT/OAuth, encryption, logging and process-local limits","Approvals, identity, credentials and bounded single-process operation."],
        ["Delivery","GitHub OAuth/PAT, Docker Compose, Nginx","Repository integration and deployable packaging."],
    ],[1750,3500,4110])

    doc.add_page_break(); section_title(doc,"5. Workflow graph and modes")
    para(doc,"The registered graph uses one main executor spine. Short read-only work may finish directly; planning, explicit interrupts, approval-controlled tools, bounded read-only workers, validation, recovery, compaction and verification are entered only when needed.")
    para(doc,REPORT_TRUTH_CLAIMS["workflow"])
    doc.add_picture(str(flow),width=Inches(6.45)); doc.inline_shapes[-1]._inline.docPr.set("descr","All registered Compass StateGraph nodes grouped into entry, planning, read-only analysis, executor, validation and verification responsibilities."); p=para(doc,"Figure 2. Registered workflow-node inventory generated from the StateGraph builder.","Caption"); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    table(doc,["Mode","Intent","Control model"],[
        ["Ask","Understand code, explain behavior or research.","Read-oriented and can answer directly."],
        ["Edit","Make bounded project changes.","Risky actions follow approval policy."],
        ["Plan","Produce a reviewable plan before acting.","Explicit plan approval gate."],
        ["Goal","Pursue a larger outcome with validation and recovery.","Multi-step progress; risky actions remain governed."],
    ],[1500,3700,4160])

    section_title(doc,"6. Problems Compass solves")
    table(doc,["Developer problem","Compass response","Value"],[
        ["Large codebases are hard to orient.","Trees, search, RAG retrieval, pinned context and history surface relevant evidence.","Faster understanding with traceable context."],
        ["Chat-only agents obscure execution.","Run rails, activity, tools, affected files and approvals make work visible.","Higher trust and easier intervention."],
        ["Review is often bolted on late.","Patches, real diff statistics, review controls, bulk actions and undo are central.","Safer changes and clearer ownership."],
        ["Delivery requires repetitive handoffs.","Repository import, branch, commit and pull request steps live in one flow.","Shorter path from task to reviewed delivery."],
        ["Hosted agents can expose local risk.","Per-user workspaces, ownership checks, path validation, shell and MCP restrictions.","A safer boundary for web development."],
    ],[2250,4400,2710])

    section_title(doc,"7. Safety and operating model")
    bullets(doc,["Read/search operations can proceed under the default policy; local writes, edits and shell commands are classified as risky.","Plan, tool and clarification requests use typed interrupts; approval actions are Execute/Revise/Cancel or Yes/No/Always/Skip as appropriate.","Hosted mode removes shell execution and rejects browser-configured command MCP servers.","Web workspaces are ownership-checked, use one explicit active workspace and reject absolute paths or traversal.",REPORT_TRUTH_CLAIMS["refresh"],"Stored provider credentials are encrypted with the configured credential key."])
    callout(doc,"IMPORTANT","AI-generated changes still require engineering review. The intended loop is: inspect context -> approve relevant side effects -> review the patch -> validate -> publish through a pull request.")

    section_title(doc,"8. Future improvements")
    para(doc,"These recommendations are proposed improvements, not claims about shipped capability.")
    table(doc,["Horizon","Recommendation","Expected outcome"],[
        ["Near term","Unify TUI slash-command metadata and handlers; add regression coverage for routing and safety decisions.","Lower maintenance cost and more reliable local operations."],
        ["Near term","Automate UI coverage for auth, command palette, review, GitHub states and responsive layouts.","Protect the completed workbench from regressions."],
        ["Next","Expand GitHub conflict, permission, retry and repository-selection recovery states.","Clearer production delivery."],
        ["Next","Add observability for stage latency, tool reliability, approvals and patch outcomes.","Evidence-based quality and cost improvements."],
        ["Later","Introduce reusable team/workflow templates after core contracts stabilize.","Composable automation without diluting the workbench."],
        ["Later","Formalize policy administration, retention controls, audit export and enterprise identity.","Stronger deployment governance."],
    ],[1450,5000,2910])

    section_title(doc,"9. Evaluation criteria")
    bullets(doc,["Task success: correct and reviewable outcomes.","Control quality: understandable context, tools, changes and approvals.","Safety: effective workspace, credential and hosted-boundary enforcement.","Delivery quality: reliable branch, commit and pull-request recovery paths.","Experience quality: accessible, responsive and readable desktop/mobile operation."])
    section_title(doc,"10. Conclusion")
    para(doc,"Compass is positioned as a controlled AI development environment. Its strongest product decision is combining automation with inspectable context, approval-aware actions, first-class patch review and an intentional route to GitHub delivery. Future work should strengthen reliability, observability and deployment governance while preserving that control model.")
    doc.save(OUTPUT); print(OUTPUT)


if __name__ == "__main__": build()
