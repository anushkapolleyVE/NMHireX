"""All actual NM-HireX business functions.

Each function is intentionally small and directly composable; LangGraph is not
required for this deterministic pipeline.
"""
import os
import shutil
import tempfile
import zipfile

import hashlib, json, re, time, logging, os, base64
from pathlib import Path
import gdown
from uuid import UUID
from sqlalchemy import select, delete, text
from sqlalchemy.orm import Session
from openai import OpenAI
from pypdf import PdfReader
from docx import Document
import pymupdf
from PIL import Image
from .config import settings
from datetime import datetime
from .models import (
    User,
    Job,
    JobRequirement,
    Candidate,
    Resume,
    CandidateSkill,
    CandidateExperience,
    CandidateEducation,
    CandidateCertification,
    CandidateProject,
    JobCandidate,
    ScreeningResult,
    ScreeningRun,
    AIExtractionLog,
    CandidateContact,
)

OPENAI_API_KEY = settings.OPENAI_API_KEY

openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
luna_client = openai_client

OCR_MODEL = "gpt-4o"


# ------------------------------------------------------------
# FILE HELPERS
# ------------------------------------------------------------
def _text_is_insufficient(text: str) -> bool:
    """Return True when native PDF extraction is too sparse to trust."""
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) < 250:
        return True

    # A page containing mostly symbols/noise is also a good OCR candidate.
    alnum = sum(ch.isalnum() for ch in cleaned)
    return alnum < max(100, int(len(cleaned) * 0.45))


def _ocr_pdf_page(page, page_number: int, native_text: str) -> str:
    """Render one PDF page and use GPT-5.6 Luna to recover only image-based text.

    Native pypdf text is preserved. Luna is asked for additional text visible
    in the page image so partial image sections are not lost or duplicated.
    """
    if luna_client is None:
        logging.warning(
            "OPENAI_API_KEY is not configured; skipping OCR for page %s.",
            page_number,
        )
        return ""

    try:
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
        image_bytes = pix.tobytes("png")
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        response = luna_client.responses.create(
            model=OCR_MODEL,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Recover text from image-based content on this CV page. "
                                "The native PDF text extracted by pypdf is provided below. "
                                "Return ONLY additional readable text that is present in the "
                                "page image but missing from the native text. This includes "
                                "image-based experience, skills, education, certifications, "
                                "projects, tables, dates, companies, job titles and other "
                                "resume information. Do not repeat text already represented "
                                "in the native text. Do not summarize. Do not invent or infer. "
                                "If the image contains no additional text, return an empty "
                                "response.\n\n"
                                f"NATIVE PDF TEXT:\n{native_text[:12000]}"
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": f"data:image/png;base64,{image_b64}",
                        },
                    ],
                }
            ],
        )

        return (response.output_text or "").strip()

    except Exception as error:
        logging.warning(
            "OCR failed for PDF page %s: %s",
            page_number,
            error,
        )
        return ""


def _read_pdf_with_ocr(path: str) -> str:
    """Extract PDF text with pypdf and OCR only pages where native text is insufficient."""
    p = Path(path)
    pypdf_logger = logging.getLogger("pypdf")
    previous_level = pypdf_logger.level

    try:
        pypdf_logger.setLevel(logging.ERROR)

        reader = PdfReader(str(p))

        extracted_text = "\n".join(
            (page.extract_text() or "")
            for page in reader.pages
        )

        if _text_is_insufficient(extracted_text):
            print(f"   [INFO] PDF {p.name} appears to be scanned. Running OCR fallback...")
            try:
                ocr_text = []
                doc = pymupdf.open(str(p))
                for page_num, page in enumerate(doc):
                    native_page_text = ""
                    if page_num < len(reader.pages):
                        native_page_text = reader.pages[page_num].extract_text() or ""
                    page_text = _ocr_pdf_page(page, page_num, native_page_text)
                    ocr_text.append(page_text)
                extracted_text = extracted_text + "\n" + "\n".join(ocr_text)
            except Exception as e:
                print(f"   [WARNING] OCR fallback failed for {p.name}: {e}")

        return extracted_text

    finally:
        pypdf_logger.setLevel(previous_level)


def read_file(path: str) -> str:
    """
    Read a supported PDF, DOCX, or TXT file.

    PDFs use pypdf first and GPT-5.6 Luna only as a fallback for
    scanned/image-heavy pages. The returned text is then passed unchanged
    into the existing JSON extraction pipeline.
    """
    p = Path(path)

    if p.suffix.lower() == ".pdf":
        return _read_pdf_with_ocr(str(p))  

    if p.suffix.lower() == ".docx":
        doc = Document(str(p))
        text_lines = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_lines.append(paragraph.text.strip())
        for table in doc.tables:
            for row in table.rows:
                row_text = []
                for cell in row.cells:
                    if cell.text.strip():
                        row_text.append(cell.text.strip().replace('\n', ' '))
                if row_text:
                    text_lines.append(" | ".join(row_text))
        return "\n".join(text_lines)

    if p.suffix.lower() == ".txt":
        return p.read_text(
            encoding="utf-8",
            errors="ignore"
        ) 

    if p.suffix.lower() in [".png", ".jpg", ".jpeg"]:
        try:
            if luna_client is None:
                raise ValueError("OPENAI_API_KEY is not configured; cannot OCR image files.")
            img = Image.open(str(p))
            from io import BytesIO
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            image_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
            response = luna_client.responses.create(
                model=OCR_MODEL,
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Extract all text from this resume image exactly as it appears. Do not add any formatting or commentary."},
                        {"type": "input_image", "image_url": f"data:image/png;base64,{image_b64}"}
                    ]
                }]
            )
            return (response.output_text or "").strip()
        except Exception as e:
            raise ValueError(f"Failed to extract text from image: {e}")

    raise ValueError(
        f"Unsupported file type: {p.suffix}"
    )

def file_hash(path: str) -> str:
    """Input: file path. Output: SHA-256 hex digest used for duplicate detection."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()



# ------------------------------------------------------------
# AI EXTRACTION
# ------------------------------------------------------------
def _json_completion(prompt: str, model: str) -> dict:
    """Input: prompt/model. Output: validated JSON object returned by the configured LLM."""
    response = openai_client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": "Return only valid JSON."}, {"role": "user", "content": prompt}],
    )
    return json.loads(response.choices[0].message.content)

def extract_jd(text: str) -> dict:
    """Input: JD text. Output: structured JD requirements. Unknown facts must be null/empty."""
    prompt = f"""
Extract this job description into JSON with exactly these keys:
job_title, min_experience_years, max_experience_years, mandatory_skills,
preferred_skills, education, certifications, domains, responsibilities,
location, work_mode, notice_period_days, other_requirements, confidence_score.
Rules: preserve specific skills exactly; only classify a skill as mandatory when
required/essential; words such as advantageous/preferred/nice-to-have belong in
preferred_skills; never infer missing experience, location, notice period or education.
JD:\n{text[:30000]}
"""
    return _json_completion(prompt, settings.EXTRACTION_MODEL)

def extract_resume(text: str) -> dict:
    """Input: CV text. Output: structured candidate profile with explicit nulls for unsupported facts."""
    prompt = f"""
Extract the CV into JSON with exactly these keys:
name, email, phone, location, total_experience_years, current_company, current_role,
notice_period_days, profile_summary, skills, experiences, education, certifications, projects.
Rules: never guess missing values; never turn a technology into a company or role;
preserve specific skills such as Django as Django and use parent_skill only as a relationship.
CV:\n{text[:30000]}
"""
    return _json_completion(prompt, settings.EXTRACTION_MODEL)

def normalize_skill(name: str) -> tuple[str, str | None, str | None]:
    """
    Normalize a candidate skill while preserving the original specific technology.

    Input:
        name -> Skill name.

    Output:
        Tuple containing:
        - normalized skill
        - parent skill
        - skill category

    Example:
        Django -> Django, Python, Backend
        DRF -> Django REST Framework, Django, Backend
    """

    if name is None:
        return "", None, None

    raw = str(name).strip()

    if not raw:
        return "", None, None

    low = raw.lower()

    relationships = {
        "django": ("Django", "Python", "Backend"),
        "django rest framework": (
            "Django REST Framework",
            "Django",
            "Backend"
        ),
        "drf": (
            "Django REST Framework",
            "Django",
            "Backend"
        ),
        "flask": ("Flask", "Python", "Backend"),
        "fastapi": ("FastAPI", "Python", "Backend"),
        "spring boot": ("Spring Boot", "Java", "Backend"),
        "react.js": ("React", "JavaScript", "Frontend"),
        "react": ("React", "JavaScript", "Frontend"),
    }

    if low in relationships:
        return relationships[low]

    return raw, None, None

def safe_list(value) -> list:
    """
    Convert an extracted value into a safe list.

    Input:
        value -> GPT extracted value.

    Output:
        Always returns a list.

    Examples:
        None -> []
        "Python" -> ["Python"]
        ["Python", "SQL"] -> ["Python", "SQL"]
        {"name": "Python"} -> [{"name": "Python"}]
    """

    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]

def safe_dict(value) -> dict:
    """
    Convert an extracted value into a safe dictionary.

    Input:
        value -> GPT extracted value.

    Output:
        Dictionary. Invalid values become {}.
    """

    return value if isinstance(value, dict) else {}
def safe_float(value):
    """
    Convert AI-extracted experience values into a PostgreSQL-safe float.

    Input:
        value -> AI-extracted value such as:
                 5
                 "5"
                 "5 years"
                 "14+"
                 "6-10"
                 "Not provided"
                 None

    Output:
        float or None
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().lower()

    if not text or text in {
        "not provided",
        "not specified",
        "unknown",
        "n/a",
        "na",
        "none",
        "null",
        "-"
    }:
        return None

    # Handle ranges such as "6-10"
    range_match = re.search(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)", text)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        return (low + high) / 2

    # Handle values such as "14+", "5 years", "3.5 years"
    number_match = re.search(r"\d+(?:\.\d+)?", text)

    if number_match:
        return float(number_match.group())

    return None
# ------------------------------------------------------------
# RESUME INGESTION
# ------------------------------------------------------------
def store_resume(db: Session, path: str, drive_url: str | None = None) -> UUID:
    """
    Store one resume safely in PostgreSQL and Pinecone.

    Input:
        db   -> SQLAlchemy PostgreSQL session
        path -> Resume file path

    Output:
        Candidate UUID.

    Processing:
        1. Detect duplicate resume.
        2. Read resume text.
        3. Extract candidate information using GPT.
        4. If extraction fails, use safe fallback data.
        5. Store candidate and resume in PostgreSQL.
        6. Store structured skills/experience/education/etc.
        7. Create Pinecone embeddings when text is available.
        8. Pinecone failure does not prevent PostgreSQL ingestion.
    """

    path_obj = Path(path)

    # ---------------------------------------------------------
    # 1. Calculate file hash
    # ---------------------------------------------------------

    digest = file_hash(path)

    existing = db.scalar(
        select(Resume).where(
            Resume.file_hash == digest
        )
    )

    if existing:
        return existing.candidate_id

    # ---------------------------------------------------------
    # 2. Read resume
    # ---------------------------------------------------------

    try:
        text = read_file(path)
    except Exception as error:
        print(
            f"   [WARNING] Could not extract text: {error}"
        )

        # We still ingest the resume.
        text = ""
    if text.strip() and looks_like_job_description(
        text,
        path_obj.name
    ):
        raise ValueError(
            "File appears to be a Job Description, not a resume"
        )
    # ---------------------------------------------------------
    # 3. Extract resume information
    # ---------------------------------------------------------

    data = {}

    if text.strip():

        try:
            extracted = extract_resume(text)

            if isinstance(extracted, dict):
                data = extracted
            else:
                print(
                    "   [WARNING] GPT returned invalid resume data."
                )

        except Exception as error:
            print(
                f"   [WARNING] Resume extraction failed: {error}"
            )

    # ---------------------------------------------------------
    # 4. Safe candidate values
    # ---------------------------------------------------------

    candidate_name = (
        data.get("name")
        or path_obj.stem
        or "Unknown Candidate"
    )

    candidate_name = str(candidate_name).strip()

    if not candidate_name:
        candidate_name = path_obj.stem or "Unknown Candidate"

    # ---------------------------------------------------------
    # 5. Create Candidate
    # ---------------------------------------------------------

    candidate = Candidate(
    name=candidate_name,
    email=data.get("email"),
    phone=data.get("phone"),
    location=data.get("location"),
    total_experience_years=safe_float(
        data.get("total_experience_years")
    ),
    current_company=data.get("current_company"),
    current_role=data.get("current_role"),
    notice_period_days=safe_float(
        data.get("notice_period_days")
    ),
    profile_summary=data.get("profile_summary"),
    raw_profile_text=text,
    normalized_profile=data,
)

    db.add(candidate)
    db.flush()

    # ---------------------------------------------------------
    # 6. Create Resume record
    # ---------------------------------------------------------

    resume = Resume(
        candidate_id=candidate.id,
        file_name=path_obj.name,
        file_url=drive_url if drive_url else str(path_obj),
        file_type=path_obj.suffix.lower().lstrip("."),
        file_size=path_obj.stat().st_size,
        file_hash=digest,
        raw_text=text,
        parsed_data=data,
        parsing_status="COMPLETED",
        extraction_status="COMPLETED",
        extraction_model=settings.EXTRACTION_MODEL,
        extraction_version="v1",
    )

    db.add(resume)
    db.flush()

    # ---------------------------------------------------------
    # 7. Store skills safely
    # ---------------------------------------------------------

    skills = safe_list(
        data.get("skills")
    )

    for item in skills:

        if isinstance(item, dict):

            name = item.get("name")

            if not name:
                continue

            normalized, parent, category = normalize_skill(
                name
            )

            if not normalized:
                continue

            db.add(
                CandidateSkill(
                    candidate_id=candidate.id,
                    skill_name=str(name),
                    normalized_skill_name=normalized,
                    parent_skill=(
                        item.get("parent_skill")
                        or parent
                    ),
                    skill_category=(
                        item.get("category")
                        or category
                    ),
                    experience_years=item.get(
                        "experience_years"
                    ),
                    proficiency=item.get(
                        "proficiency"
                    ),
                    source="resume",
                    confidence_score=item.get(
                        "confidence_score"
                    ),
                )
            )

        elif isinstance(item, str):

            normalized, parent, category = normalize_skill(
                item
            )

            if not normalized:
                continue

            db.add(
                CandidateSkill(
                    candidate_id=candidate.id,
                    skill_name=item.strip(),
                    normalized_skill_name=normalized,
                    parent_skill=parent,
                    skill_category=category,
                    source="resume",
                )
            )

    # ---------------------------------------------------------
    # 8. Store experience safely
    # ---------------------------------------------------------

    experiences = safe_list(
        data.get("experiences")
        or data.get("experience")
    )

    for item in experiences:

        if isinstance(item, str):
            item = {
                "description": item
            }

        if not isinstance(item, dict):
            continue

        db.add(
            CandidateExperience(
                candidate_id=candidate.id,
                company_name=item.get(
                    "company_name"
                ),
                job_title=item.get(
                    "job_title"
                ),
                employment_type=item.get(
                    "employment_type"
                ),
                description=item.get(
                    "description"
                ),
                domain=item.get(
                    "domain"
                ),
                normalized_data=item,
            )
        )

    # ---------------------------------------------------------
    # 9. Store education safely
    # ---------------------------------------------------------

    education = safe_list(
        data.get("education")
    )

    for item in education:

        if isinstance(item, str):
            item = {
                "degree": item
            }

        if not isinstance(item, dict):
            continue

        db.add(
            CandidateEducation(
                candidate_id=candidate.id,
                degree=item.get(
                    "degree"
                ),
                field_of_study=item.get(
                    "field_of_study"
                ),
                institution=item.get(
                    "institution"
                ),
                start_year=item.get(
                    "start_year"
                ),
                end_year=item.get(
                    "end_year"
                ),
                grade=item.get(
                    "grade"
                ),
            )
        )

    # ---------------------------------------------------------
    # 10. Store certifications safely
    # ---------------------------------------------------------

    certifications = safe_list(
        data.get("certifications")
    )

    for item in certifications:

        if isinstance(item, str):
            item = {
                "certification_name": item
            }

        if not isinstance(item, dict):
            continue

        certification_name = (
            item.get("certification_name")
            or item.get("name")
        )

        if not certification_name:
            continue

        db.add(
            CandidateCertification(
                candidate_id=candidate.id,
                certification_name=certification_name,
                issuing_organization=(
                    item.get(
                        "issuing_organization"
                    )
                    or item.get("issuer")
                ),
                credential_id=item.get(
                    "credential_id"
                ),
            )
        )

    # ---------------------------------------------------------
    # 11. Store projects safely
    # ---------------------------------------------------------

    projects = safe_list(
        data.get("projects")
    )

    for item in projects:

        if isinstance(item, str):
            item = {
                "project_name": item
            }

        if not isinstance(item, dict):
            continue

        db.add(
            CandidateProject(
                candidate_id=candidate.id,
                project_name=item.get(
                    "project_name"
                ),
                description=item.get(
                    "description"
                ),
                technologies=item.get(
                    "technologies"
                ),
                domain=item.get(
                    "domain"
                ),
            )
        )

    # ---------------------------------------------------------
    # 12. Commit PostgreSQL FIRST
    # ---------------------------------------------------------

    db.commit()

    print("   [OK] PostgreSQL")
    return candidate.id
def looks_like_job_description(text: str, filename: str) -> bool:
    """
    Detect whether a file is more likely to be a Job Description than a resume.

    Input:
        text     -> extracted document text
        filename -> original filename

    Output:
        True if the document appears to be a JD, otherwise False.
    """
    filename_lower = filename.lower()
    text_lower = text.lower()

    # Strong filename indicators
    jd_filename_terms = [
        "job description",
        "job_description",
        "jd_",
        "_jd",
        " jd",
    ]

    if any(term in filename_lower for term in jd_filename_terms):
        return True

    # Strong JD content indicators
    jd_terms = [
        "job description",
        "role overview",
        "role context",
        "responsibilities",
        "qualifications",
        "requirements",
        "key responsibilities",
        "preferred qualifications",
        "job requirements",
    ]

    matches = sum(1 for term in jd_terms if term in text_lower)

    return matches >= 3

# -------------------------------------------
#     # ingest resume folder 
# -------------------------------------------

def ingest_resume_folder(db: Session, custom_dir: str | None = None, drive_url: str | None = None) -> dict:
    """
    Ingest all resumes from a directory. and ingest every supported CV.

    Input:
        db -> SQLAlchemy PostgreSQL database session
        custom_dir -> Optional path to scan instead of settings.RESUME_DIR
        drive_url -> Optional Google Drive URL for the resume

    Output:
        Dictionary containing:
        - total
        - successful
        - skipped
        - failed
        - failed_files

    Processing:
        1. Scan data/resumes.
        2. Process every PDF/DOCX.
        3. Store every readable or partially readable CV.
        4. Continue even when extraction fails.
        5. Continue even when Pinecone fails.
    """

    resume_dir = Path(custom_dir) if custom_dir else Path(settings.RESUME_DIR)

    if not resume_dir.exists():

        return {
            "status": "FAILED",
            "message": (
                f"Resume directory does not exist: "
                f"{resume_dir}"
            ),
            "total": 0,
            "successful": 0,
            "skipped": 0,
            "failed": 0,
            "failed_files": [],
        }

    files = sorted(
        [
            p
            for p in resume_dir.rglob("*")
            if p.is_file()
            and p.suffix.lower() in {
                ".pdf",
                ".docx",
                ".txt",
                ".png",
                ".jpg",
                ".jpeg"
            }
        ],
        key=lambda p: p.name.lower(),
    )

    total = len(files)

    successful = 0
    skipped = 0
    failed = 0

    failed_files = []

    print()
    print("=" * 70)
    print(f"FOUND {total} RESUME FILES")
    print("=" * 70)

    for index, file_path in enumerate(
        files,
        start=1
    ):

        print(
            f"\n[{index}/{total}] "
            f"Processing: {file_path.name}"
        )

        try:

            # -------------------------------------------------
            # Duplicate check
            # -------------------------------------------------

            digest = file_hash(
                str(file_path)
            )

            existing = db.scalar(
                select(Resume).where(
                    Resume.file_hash == digest
                )
            )

            if existing:

                print(
                    "   [SKIPPED] Already ingested."
                )

                skipped += 1
                continue

            # -------------------------------------------------
            # Store resume
            # -------------------------------------------------

            candidate_id = store_resume(
                db=db,
                path=str(file_path),
                drive_url=drive_url
            )

            successful += 1

            print(
                f"   [OK] Successfully ingested "
                f"| Candidate: {candidate_id}"
            )

        except ValueError as error:
                db.rollback()

                if "Job Description" in str(error):
                    skipped += 1
                    print(f"   [SKIPPED] {file_path.name} - Job Description detected.")
                else:
                    failed += 1
                    failed_files.append({
                        "file": file_path.name,
                        "error": str(error)
                    })
                    print(f"   [FAILED] {file_path.name}")
                    print(f"   Reason: {error}")

                continue

        except Exception as error:
            db.rollback()
            failed += 1
            failed_files.append({
                "file": file_path.name,
                "error": str(error)
            })
            print(f"   [FAILED] {file_path.name}")
            print(f"   Reason: {error}")
            continue

    # ---------------------------------------------------------
    # Final summary
    # ---------------------------------------------------------

    print()
    print("=" * 70)
    print("RESUME INGESTION COMPLETE")
    print("=" * 70)

    print(
        f"Total files : {total}"
    )

    print(
        f"Successful  : {successful}"
    )

    print(
        f"Skipped     : {skipped}"
    )

    print(
        f"Failed      : {failed}"
    )

    if failed_files:

        print()
        print("FAILED FILES")
        print("-" * 70)

        for item in failed_files:

            print(
                f"- {item['file']}"
            )

            print(
                f"  {item['error']}"
            )

    print("=" * 70)

    return {
        "status": "COMPLETED",
        "total": total,
        "successful": successful,
        "skipped": skipped,
        "failed": failed,
        "failed_files": failed_files,
    }

def sync_google_drive(db: Session, url: str) -> dict:
    """
    Sync resumes from a Google Drive URL.
    Assuming the URL points to a shared Folder or a ZIP file.
    """
    temp_dir = tempfile.mkdtemp()
    
    try:
        if "drive.google.com/drive/folders/" in url:
            gdown.download_folder(url, output=temp_dir, quiet=False, use_cookies=False)
            return ingest_resume_folder(db, custom_dir=temp_dir, drive_url=url)
        else:
            cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                output_path = gdown.download(url, quiet=False)
                
                if output_path and zipfile.is_zipfile(output_path):
                    with zipfile.ZipFile(output_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                    os.remove(output_path)
            finally:
                os.chdir(cwd)
            
            return ingest_resume_folder(db, custom_dir=temp_dir, drive_url=url)
    except Exception as e:
        return {
            "status": "FAILED",
            "message": f"Failed to download or process Google Drive link: {str(e)}",
            "total": 0, "successful": 0, "skipped": 0, "failed": 0, "failed_files": []
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
# ------------------------------------------------------------
# JD CREATION
# ------------------------------------------------------------
def create_job(
    db: Session,
    user_id: UUID,
    raw_text: str,
    file_name: str | None = None,
    file_path: str | None = None
) -> Job:
    """
    Create a Job from either written JD text or an uploaded JD file.

    Input:
        db        -> PostgreSQL database session
        user_id   -> authenticated recruiter/user UUID
        raw_text  -> JD text
        file_name -> optional uploaded JD filename
        file_path -> optional path of uploaded JD file

    Output:
        Persisted Job with JobRequirement and AIExtractionLog.
    """

    def _safe_float(val):
        try:
            if isinstance(val, dict):
                val = val.get("max", val.get("min", val.get("value", None)))
            return float(val) if val is not None else None
        except (ValueError, TypeError):
            return None

    def _safe_int(val):
        try:
            if isinstance(val, dict):
                val = val.get("max", val.get("min", val.get("value", None)))
            return int(float(val)) if val is not None else None
        except (ValueError, TypeError):
            return None

    if not raw_text or not raw_text.strip():
        raise ValueError("JD content cannot be empty")

    raw_text = raw_text.strip()

    # --------------------------------------------------------
    # 1. Extract JD requirements using GPT
    # --------------------------------------------------------
    data = extract_jd(raw_text)

    # --------------------------------------------------------
    # 2. Create Job
    # --------------------------------------------------------
    job = Job(
        created_by=user_id,
        title=data.get("job_title") or "Untitled Job",
        description=raw_text,
        location=data.get("location"),
        work_mode=data.get("work_mode"),
        jd_file_name=file_name,
        jd_file_url=file_path,
        jd_raw_text=raw_text,
        status="READY"
    )

    db.add(job)
    db.flush()

    # --------------------------------------------------------
    # 3. Store extracted JD requirements
    # --------------------------------------------------------
    req = JobRequirement(
        job_id=job.id,
        job_title=data.get("job_title"),

        minimum_experience=_safe_float(data.get("min_experience_years")),
        maximum_experience=_safe_float(data.get("max_experience_years")),

        location=data.get("location") if isinstance(data.get("location"), str) else None,
        work_mode=data.get("work_mode") if isinstance(data.get("work_mode"), str) else None,
        notice_period_days=_safe_int(data.get("notice_period_days")),

        mandatory_skills=data.get("mandatory_skills") or [],
        preferred_skills=data.get("preferred_skills") or [],

        education=data.get("education") or [],
        certifications=data.get("certifications") or [],
        domains=data.get("domains") or [],
        responsibilities=data.get("responsibilities") or [],

        other_requirements=data.get("other_requirements") or [],

        extraction_model=settings.EXTRACTION_MODEL,
        extraction_version="v1",
        confidence_score=safe_float(data.get("confidence_score"))
    )

    db.add(req)

    # --------------------------------------------------------
    # 4. Store AI extraction log
    # --------------------------------------------------------
    db.add(
        AIExtractionLog(
            entity_type="JD",
            entity_id=job.id,
            model_name=settings.EXTRACTION_MODEL,
            prompt_version="v1",
            input_text_hash=hashlib.sha256(
                raw_text.encode()
            ).hexdigest(),
            output_data=data,
            confidence_score=safe_float(data.get("confidence_score")),
            validation_status="PASSED"
        )
    )

    # --------------------------------------------------------
    # 5. Save everything
    # --------------------------------------------------------
    db.commit()
    db.refresh(job)

    return job

# ------------------------------------------------------------
# MATCHING + EVIDENCE
# ------------------------------------------------------------


# def exact_skill_match(db: Session, candidate_id: UUID, required: list) -> dict:
#     """Input: candidate and JD required skills. Output: per-skill match evidence and percentage."""
#     skills = db.scalars(select(CandidateSkill).where(CandidateSkill.candidate_id == candidate_id)).all()
#     normalized = {s.normalized_skill_name.lower(): s for s in skills}
#     parent_map = {s.parent_skill.lower(): s for s in skills if s.parent_skill}
#     details, matched = [], 0
#     required_names = [x.get("name") if isinstance(x, dict) else str(x) for x in required]
#     for req in required_names:
#         key = req.lower()
#         if key in normalized:
#             matched += 1; details.append({"required": req, "status": "EXACT", "candidate_skill": normalized[key].skill_name})
#         elif key in parent_map:
#             details.append({"required": req, "status": "PARENT_SUPPORT", "candidate_skill": parent_map[key].skill_name})
#         else:
#             details.append({"required": req, "status": "MISSING"})
#     return {"matched": matched, "total": len(required_names), "details": details}


def exact_skill_match(db: Session, candidate_id: UUID, required: list) -> dict:

    """

    Match JD-required skills against candidate skills.
 
    Uses database-normalized skill names and parent skills.

    No hardcoded skill aliases.
 
    Match priority:

        EXACT > PARENT_SUPPORT > MISSING
 
    Only EXACT matches count toward the percentage.

    """
 
    # Get candidate skills

    skills = db.scalars(

        select(CandidateSkill).where(

            CandidateSkill.candidate_id == candidate_id

        )

    ).all()
 
    # Prepare candidate skills from DB

    candidate_skills = []
 
    for skill in skills:

        normalized = (skill.normalized_skill_name or skill.skill_name or "").strip().lower()

        original = (skill.skill_name or "").strip()

        parent = (skill.parent_skill or "").strip().lower()
 
        candidate_skills.append({

            "normalized": normalized,

            "original": original,

            "parent": parent,

        })
 
    # Extract required skill names

    required_names = [

        x.get("name") if isinstance(x, dict) else str(x)

        for x in required

    ]
 
    details = []

    matched = 0
 
    for req in required_names:
 
        required_skill = str(req).strip().lower()
 
        status = "MISSING"

        matched_skill_name = None
 
        # ---------------------------------------------------------

        # 1. EXACT NORMALIZED MATCH

        # ---------------------------------------------------------

        for candidate in candidate_skills:
 
            if required_skill == candidate["normalized"]:

                status = "EXACT"

                matched_skill_name = candidate["original"]

                break
 
        # ---------------------------------------------------------

        # 2. PARENT SKILL MATCH

        # ---------------------------------------------------------

        if status == "MISSING":
 
            for candidate in candidate_skills:
 
                if (

                    candidate["parent"]

                    and required_skill == candidate["parent"]

                ):

                    status = "PARENT_SUPPORT"

                    matched_skill_name = candidate["original"]

                    break
 
        # Only exact matches count

        if status == "EXACT":

            matched += 1
 
        details.append({

            "required": req,

            "status": status,

            "candidate_skill": matched_skill_name,

        })
 
    # Calculate percentage

    total = len(required_names)
 
    percentage = (

        round((matched / total) * 100, 2)

        if total > 0

        else 0

    )
 
    return {

        "matched": matched,

        "total": total,

        "percentage": percentage,

        "details": details,

    }
 
def retrieve_evidence(db: Session, candidate_id: UUID) -> list[dict]:
    """Input: candidate UUID. Output: profile summary from PostgreSQL as evidence."""
    candidate = db.get(Candidate, candidate_id)
    if candidate and candidate.profile_summary:
        return [{"score": 1.0, "text": candidate.profile_summary}]
    return [{"score": 0.0, "text": "No evidence available."}]

# ------------------------------------------------------------
# GPT EVALUATION
# ------------------------------------------------------------
def nl_to_sql_search(req: JobRequirement) -> str:
    """Output: PostgreSQL query to find matching candidate UUIDs loosely."""
    req_json = {
        "mandatory_skills": req.mandatory_skills,
        "preferred_skills": req.preferred_skills,
        "min_experience_years": req.minimum_experience
    }
    prompt = f"""
You are a PostgreSQL expert. Generate a SQL query to find candidates who MIGHT match this Job Requirement.
Database Schema:
- candidates (id UUID, name VARCHAR, total_experience_years NUMERIC, location VARCHAR, notice_period_days INT)
- candidate_skills (candidate_id UUID, skill_name VARCHAR)
- candidate_experiences (candidate_id UUID, job_title VARCHAR)
Rules:
- Return distinct `candidates.id`.
- Be loose/forgiving: we want to cast a wide net. For example, if minimum experience is 8, maybe accept >= 6.
- If skills are listed, match candidates who have AT LEAST ONE of the mandatory or preferred skills using ILIKE on `candidate_skills.skill_name`.
- Do NOT wrap the query in markdown formatting (like ```sql).
- Return ONLY the raw SQL string.
Requirements:
{json.dumps(req_json, default=str)}
"""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        sql_query = response.choices[0].message.content.strip()
        sql_query = re.sub(r"^```sql", "", sql_query, flags=re.IGNORECASE)
        return re.sub(r"```$", "", sql_query).strip()
    except Exception as e:
        print(f"NL-to-SQL failed: {e}")
        raise e

# ------------------------------------------------------------
# GPT EVALUATION
# ------------------------------------------------------------
def ai_score_candidate(payload: dict) -> dict:
    """Output: precisely 8 numerical scores and reasoning string."""
    prompt = f"""
You are an expert AI Recruiter evaluating a candidate against a job description.
Assign precise numerical scores for each of the following 8 criteria, adhering strictly to the maximum points allowed for each.

Criteria & Maximum Points:
1. mandatory_skills_score: max 30
2. experience_score: max 25
3. domain_score: max 15
4. preferred_skills_score: max 10
5. education_score: max 5
6. location_score: max 5
7. availability_score: max 5
8. other_requirements_score: max 5

Rules:
- Be realistic and precise. Give partial points if they partially meet a requirement.
- If the JD does not mention a requirement (e.g., no location specified), award full points for that category.
- Output ONLY a JSON object with EXACTLY the keys listed above (as numbers), plus a string key 'reasoning' explaining the scores briefly.
DATA:\n{json.dumps(payload, default=str)}
"""
    return _json_completion(prompt, settings.EVALUATION_MODEL)

# ------------------------------------------------------------
# DETERMINISTIC SCORING
# ------------------------------------------------------------
def calculate_score(evaluation: dict) -> dict:
    """Input: evaluation dict with 8 numeric scores. Output: fixed 100-point score and classification."""
    try:
        mandatory = float(evaluation.get("mandatory_skills_score", 0))
        experience = float(evaluation.get("experience_score", 0))
        domain = float(evaluation.get("domain_score", 0))
        preferred = float(evaluation.get("preferred_skills_score", 0))
        education = float(evaluation.get("education_score", 0))
        location = float(evaluation.get("location_score", 0))
        availability = float(evaluation.get("availability_score", 0))
        other = float(evaluation.get("other_requirements_score", 0))
    except (ValueError, TypeError):
        mandatory, experience, domain, preferred, education, location, availability, other = 0,0,0,0,0,0,0,0
    total = round(mandatory + experience + domain + preferred + education + location + availability + other, 2)
    if total >= 90: classification = "EXCELLENT_MATCH"
    elif total >= 80: classification = "STRONG_MATCH"
    elif total >= 70: classification = "GOOD_MATCH"
    elif total >= 60: classification = "MODERATE_MATCH"
    else: classification = "LOW_MATCH_DO_NOT_PRIORITIZE"
    return {"mandatory_skills_score": mandatory, "experience_score": experience, "domain_score": domain,
            "preferred_skills_score": preferred, "education_score": education, "location_score": location,
            "availability_score": availability, "other_requirements_score": other, "total_score": total,
            "classification": classification}

# ------------------------------------------------------------
# SCREENING ORCHESTRATION
# ------------------------------------------------------------
def screen_job(db: Session, job_id: UUID) -> dict:
    """Input: DB session and JD UUID. Output: persisted ranking and Top 10 summary."""
    job = db.get(Job, job_id)
    if not job or not job.requirements:
        raise ValueError("Job or extracted requirements not found")
    req = job.requirements
    run = ScreeningRun(job_id=job.id, status="RUNNING", current_stage="SEARCHING", started_at=time_now())
    db.add(run); job.status = "SEARCHING"; db.commit()
    try:
        try:
            sql_query = nl_to_sql_search(req)
            result = db.execute(text(sql_query))
            candidate_ids = [UUID(str(row[0])) for row in result.fetchall()]
        except Exception as e:
            db.rollback()
            print(f"SQL execution failed: {e}. Searching failed.")
            run.status = "FAILED"
            run.current_stage = "COMPLETED"
            run.completed_at = time_now()
            job.status = "ACTIVE"
            db.commit()
            raise Exception("Searching failed")
            
        if not candidate_ids:
            print("No candidates found. Skipping scoring.")
            run.status = "COMPLETED"
            run.current_stage = "COMPLETED"
            run.completed_at = time_now()
            job.status = "ACTIVE"
            db.commit()
            return {"job_id": str(job.id), "candidates_evaluated": 0, "top_10": []}
            
        candidate_ids = list(set(candidate_ids))
        run.total_candidates = len(candidate_ids); run.current_stage = "EVALUATING"; db.commit()
        import concurrent.futures
        scoring_tasks = []
        for cid in candidate_ids:
            candidate = db.get(Candidate, cid)
            if not candidate:
                continue
            payload = {
                "candidate": {"name": candidate.name, "experience": candidate.total_experience_years,
                              "company": candidate.current_company, "role": candidate.current_role,
                              "location": candidate.location, "notice_period_days": candidate.notice_period_days,
                              "profile": candidate.profile_summary},
                "requirements": {"min_experience": req.minimum_experience, "max_experience": req.maximum_experience,
                                  "mandatory_skills": req.mandatory_skills, "preferred_skills": req.preferred_skills,
                                  "education": req.education, "certifications": req.certifications, "domains": req.domains,
                                  "responsibilities": req.responsibilities, "location": req.location, "work_mode": req.work_mode,
                                  "notice_period_days": req.notice_period_days, "other_requirements": req.other_requirements}
            }
            scoring_tasks.append((cid, payload))

        ranked = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_cid = {executor.submit(ai_score_candidate, task[1]): task[0] for task in scoring_tasks}
            
            for future in concurrent.futures.as_completed(future_to_cid):
                cid = future_to_cid[future]
                try:
                    evaluation = future.result()
                    score = calculate_score(evaluation)
                    jc = db.scalar(select(JobCandidate).where(JobCandidate.job_id == job.id, JobCandidate.candidate_id == cid))
                    if not jc:
                        jc = JobCandidate(job_id=job.id, candidate_id=cid)
                        db.add(jc); db.flush()
                    jc.eligibility_status = "ELIGIBLE" if score["total_score"] >= 60 else "INELIGIBLE"
                    jc.recruitment_status = "SCREENED"
                    jc.overall_score = score["total_score"]; jc.classification = score["classification"]
                    result_record = db.scalar(select(ScreeningResult).where(ScreeningResult.job_candidate_id == jc.id))
                    if not result_record:
                        result_record = ScreeningResult(job_candidate_id=jc.id, classification=score["classification"])
                        db.add(result_record)
                    for key in ["mandatory_skills_score","experience_score","domain_score","preferred_skills_score","education_score","location_score","availability_score","other_requirements_score","total_score","classification"]:
                        setattr(result_record, key, score[key])
                    result_record.matching_details = {"evaluation": evaluation.get("reasoning")}
                    result_record.semantic_matches = []
                    result_record.missing_requirements = []
                    result_record.strengths = []
                    result_record.concerns = []
                    result_record.screening_model = settings.EVALUATION_MODEL; result_record.screening_version = "v2"
                    ranked.append((jc, score))
                    run.successful_candidates += 1
                except Exception as e:
                    print(f"Candidate scoring failed: {e}")
                    run.failed_candidates += 1
                run.processed_candidates += 1
                db.commit()
        ranked.sort(key=lambda x: x[1]["total_score"], reverse=True)
        for position, (jc, score) in enumerate(ranked, 1):
            jc.ranking_position = position
            jc.is_shortlisted = position <= settings.TOP_N
            db.add(jc)
        job.status = "ACTIVE"; run.status = "COMPLETED"; run.current_stage = "COMPLETED"; run.completed_at = time_now()
        db.commit()
        return {"job_id": str(job.id), "candidates_evaluated": len(ranked), "top_10": get_job_candidates(db, job.id, limit=settings.TOP_N)}
    except Exception as exc:
        db.rollback(); run.status = "FAILED"; run.error_message = str(exc); run.completed_at = time_now(); job.status = "DRAFT"; db.commit(); raise

def time_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)

# ------------------------------------------------------------
# QUERY FUNCTIONS
# ------------------------------------------------------------
def get_job_candidates(db: Session, job_id: UUID, limit: int = 10) -> list[dict]:
    """
    Input: job UUID.
    Output: ranked candidates with complete score breakdown
    for frontend screening card.
    """

    rows = db.execute(
        select(JobCandidate, Candidate, ScreeningResult)
        .join(
            Candidate,
            Candidate.id == JobCandidate.candidate_id
        )
        .join(
            ScreeningResult,
            ScreeningResult.job_candidate_id == JobCandidate.id
        )
        .where(
            JobCandidate.job_id == job_id,
            JobCandidate.is_shortlisted == True
        )
        .order_by(JobCandidate.ranking_position)
    ).all()

    results = []

    for jc, candidate, screening in rows[:limit]:

        # Convert weighted scores into frontend percentages.
        # Example: 24/30 = 80%.
        mandatory = float(screening.mandatory_skills_score or 0)
        experience = float(screening.experience_score or 0)
        domain = float(screening.domain_score or 0)
        preferred = float(screening.preferred_skills_score or 0)
        education = float(screening.education_score or 0)
        location = float(screening.location_score or 0)
        availability = float(screening.availability_score or 0)
        other = float(screening.other_requirements_score or 0)

        score_breakdown = {
            "mandatory_skills": {
                "score": mandatory,
                "max_score": 30,
                "percentage": round((mandatory / 30) * 100)
            },
            "experience": {
                "score": experience,
                "max_score": 25,
                "percentage": round((experience / 25) * 100)
            },
            "domain": {
                "score": domain,
                "max_score": 15,
                "percentage": round((domain / 15) * 100)
            },
            "preferred_skills": {
                "score": preferred,
                "max_score": 10,
                "percentage": round((preferred / 10) * 100)
            },
            "education": {
                "score": education,
                "max_score": 5,
                "percentage": round((education / 5) * 100)
            },
            "location": {
                "score": location,
                "max_score": 5,
                "percentage": round((location / 5) * 100)
            },
            "availability": {
                "score": availability,
                "max_score": 5,
                "percentage": round((availability / 5) * 100)
            },
            "other_requirements": {
                "score": other,
                "max_score": 5,
                "percentage": round((other / 5) * 100)
            }
        }

        # Reasoning was stored inside matching_details.
        reasoning = None

        if screening.matching_details:
            reasoning = screening.matching_details.get("evaluation")

        resume = db.execute(select(Resume).where(Resume.candidate_id == candidate.id).order_by(Resume.uploaded_at.desc())).scalars().first()
        resume_url = resume.file_url if resume else None

        results.append({
            "rank": jc.ranking_position,
            "candidate_id": str(candidate.id),  
            "name": candidate.name,
            "email": candidate.email,
            "phone": candidate.phone,
            "resume_url": resume_url,

            # Candidate information for frontend
            "experience_years": (
                float(candidate.total_experience_years)
                if candidate.total_experience_years is not None
                else None
            ),
            "current_company": candidate.current_company,
            "current_role": candidate.current_role,
            "location": candidate.location,
            "notice_period_days": candidate.notice_period_days,
            "skills": (
                candidate.normalized_profile.get("skills", [])
                if candidate.normalized_profile
                else []
            ),
            "experience_details": (
                candidate.normalized_profile.get("experiences", [])
                if candidate.normalized_profile
                else []
            ),
            # Overall result
            "score": float(screening.total_score or 0),
            "classification": screening.classification,
            "status": jc.recruitment_status,

            # Detailed scoring
            "score_breakdown": score_breakdown,

            # AI explanation
            "reasoning": reasoning
        })

    return results
 
def get_user_jobs(db: Session, user_id: UUID) -> list[dict]:
    """Input: authenticated user UUID. Output: only that user's JDs."""
    jobs = db.scalars(select(Job).where(Job.created_by == user_id).order_by(Job.created_at.desc())).all()
    return [{"job_id": str(j.id), "title": j.title, "file_name": j.jd_file_name, "status": j.status,
             "created_at": j.created_at.isoformat() if j.created_at else None} for j in jobs]

def get_user_job_candidates(db: Session, user_id: UUID, job_id: UUID) -> list[dict]:
    """Input: authenticated user and job UUID. Output: Top 10 only when the user owns the JD."""
    if not db.scalar(select(Job.id).where(Job.id == job_id, Job.created_by == user_id)):
        raise PermissionError("Job does not belong to current user")
    return get_job_candidates(db, job_id)

def get_admin_jobs(db: Session) -> list[dict]:
    """Input: DB session. Output: all JDs with uploader and Top 10 summary."""
    rows = db.execute(select(Job, User).join(User, User.id == Job.created_by).order_by(Job.created_at.desc())).all()
    return [{"job_id": str(j.id), "title": j.title, "file_name": j.jd_file_name, "status": j.status,
             "uploaded_by": {"id": str(u.id), "name": u.name, "email": u.email},
             "top_10": get_job_candidates(db, j.id)} for j, u in rows]

def get_admin_job_candidates(db: Session, job_id: UUID) -> list[dict]:
    """Input: job UUID. Output: Top 10 persisted candidates for that JD."""
    if not db.get(Job, job_id):
        raise ValueError("Job not found")
    return get_job_candidates(db, job_id)

def get_user_dashboard(db: Session, user_id: UUID) -> dict:
    """Input: user UUID. Output: aggregate dashboard stats and pipeline."""
    user = db.get(User, user_id)
    if not user:
        raise ValueError("User not found")
        
    jobs = db.scalars(select(Job).where(Job.created_by == user_id).order_by(Job.created_at.desc())).all()
    active_jobs = len(jobs)
    
    total_screened = 0
    strong_matches = 0
    whatsapp_outreach = 0
    
    pipeline = []
    
    for j in jobs:
        candidates = get_job_candidates(db, j.id)
        screened_count = len(candidates)
        total_screened += screened_count
        
        strong_count = sum(1 for c in candidates if c.get("score", 0) >= 80)
        strong_matches += strong_count
        
        exp_str = "N/A"
        if j.requirements:
            min_exp = j.requirements.minimum_experience
            max_exp = j.requirements.maximum_experience
            if min_exp and max_exp: 
                exp_str = f"{int(min_exp)}-{int(max_exp)} yrs"
            elif min_exp: 
                exp_str = f"{int(min_exp)}+ yrs"
                
        pipeline.append({
            "job_id": str(j.id),
            "title": j.title,
            "location": j.location or "Remote",
            "experience": exp_str,
            "sources": "Database",
            "screened": screened_count,
            "strong": strong_count,
            "outreach_count": 0,
            "outreach_total": screened_count,
            "status": j.status
        })
        
    return {
        "user_name": user.name,
        "metrics": {
            "active_jobs": active_jobs,
            "candidates_screened": total_screened,
            "strong_matches": strong_matches,
            "whatsapp_outreach": whatsapp_outreach
        },
        "pipeline": pipeline[:5]
    }

def _send_whatsapp_to_candidate(
    db: Session,
    job_id: UUID,
    candidate_id: UUID,
    target_phone: str | None = None
):
    print(f"--- Attempting WhatsApp Integration for candidate {candidate_id} ---")
    try:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            print("Candidate not found in DB.")
            return

        import urllib.request
        import json

        # Find the JobCandidate record
        job_candidate = db.scalar(
            select(JobCandidate).where(
                JobCandidate.job_id == job_id,
                JobCandidate.candidate_id == candidate_id
            )
        )

        if not job_candidate:
            print("JobCandidate not found.")
            return

        
        # Use target_phone if provided, else use stage number if configured, otherwise use candidate's phone
        raw_phone = target_phone
        if not raw_phone:
            raw_phone = getattr(settings, "WHATSAPP_STAGE_NUMBER", None)
        if not raw_phone:
            raw_phone = str(candidate.phone) if candidate.phone else ""
            
        if not raw_phone or raw_phone == "None":
            print("No phone number available for candidate (and no stage number configured). Skipping.")
            return

        clean_phone = ''.join(filter(str.isdigit, raw_phone))
        
        if clean_phone:
            if len(clean_phone) == 10:
                clean_phone = "91" + clean_phone
            
            url = "https://nmve.io/whatsapp/api/integrations/whatsapp/messages"
            headers = {
                "Content-Type": "application/json"
            }
            if getattr(settings, "WHATSAPP_API_KEY", ""):
                headers["Authorization"] = f"Bearer {settings.WHATSAPP_API_KEY}"
                headers["api-key"] = settings.WHATSAPP_API_KEY
            
            payload = {
                "to": clean_phone,
                "type": "template",
  "template": {
    "name": "hello_world",
    "language": {
      "code": "en_US"
    }
  },
                "referenceId": f"NMHireX-{str(candidate_id)[:8]}",
                "callbackUrl": "https://nmhirex.onrender.com/api/webhooks/whatsapp"
            }
            
            print(f"Sending WhatsApp payload to {clean_phone}...")
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            
            try:
                with urllib.request.urlopen(req) as response:
                    response_body = response.read().decode('utf-8')

                    print(
                        f"WhatsApp message sent to {clean_phone}, "
                        f"status: {response.status}"
                    )
                    print(f"Response: {response_body}")

                    # Save outgoing WhatsApp message in candidate_contacts
                    contact = CandidateContact(
                        job_candidate_id=job_candidate.id,
                        channel="WHATSAPP",
                        message_type="OUTBOUND",
                        message="Hi",
                        provider="NMVE",
                        status="SENT",
                        sent_at=datetime.utcnow(),
                    )

                    db.add(contact)
                    db.commit()

                    print("WhatsApp message saved to candidate_contacts.")

            except urllib.error.HTTPError as http_err:
                error_body = http_err.read().decode('utf-8')
                print(f"WhatsApp API HTTP Error: {http_err.code}")
                print(f"Error Details: {error_body}")

            except Exception as api_err:
                print(f"WhatsApp API Error: {api_err}")

        else:
            print("Phone number is invalid or empty after cleaning.")

    except Exception as e:
        print(f"Error in WhatsApp integration: {e}")


def mark_candidate_contacted(
    db: Session,
    job_id: UUID,
    candidate_id: UUID,
    target_phone: str | None = None
):
    update_candidate_status(
        db,
        job_id,
        candidate_id,
        'CONTACTED',
        target_phone
    )

def get_outreach_candidates(db: Session, user_id: UUID) -> list[dict]:
    # Get all candidates who have been contacted, interested,
    # not interested, or have received an interview link.
    rows = db.execute(
        select(JobCandidate, Job, Candidate)
        .join(Job, Job.id == JobCandidate.job_id)
        .join(Candidate, Candidate.id == JobCandidate.candidate_id)
        .where(
            JobCandidate.recruitment_status.in_([
                'CONTACTED',
                'INTERESTED',
                'NOT_INTERESTED',
                'INTERVIEW_LINK_SENT'
            ])
        )
        .order_by(JobCandidate.updated_at.desc())
    ).all()

    results = []

    for jc, job, candidate in rows:

        # Find the latest WhatsApp response from this candidate
        latest_response = (
            db.query(CandidateContact)
            .filter(
                CandidateContact.job_candidate_id == jc.id,
                CandidateContact.channel == "WHATSAPP",
                CandidateContact.message_type == "INBOUND"
            )
            .order_by(
                CandidateContact.created_at.desc()
            )
            .first()
        )

        response_text = None
        response_intent = None
        responded_at = None

        if latest_response:
            response_text = (
                latest_response.response_text
                or latest_response.message
            )

            # Intent will be populated by the WhatsApp webhook
            response_intent = getattr(
                latest_response,
                "response_intent",
                None
            )

            responded_at = latest_response.responded_at

        results.append({
            "id": str(candidate.id),
            "job_id": str(job.id),
            "job_candidate_id": str(jc.id),
            "name": candidate.name or "Unnamed Candidate",
            "job": job.title or "Unknown Role",
            "status": jc.recruitment_status,

            # WhatsApp response information
            "response_text": response_text,
            "response_intent": response_intent,
            "responded_at": (
                responded_at.isoformat()
                if responded_at
                else None
            )
        })

    return results

def update_candidate_status(db: Session, job_id: UUID, candidate_id: UUID, status: str, target_phone: str | None = None):
    db.execute(
        text("UPDATE job_candidates SET recruitment_status = :status, updated_at = now() WHERE job_id = :job_id AND candidate_id = :candidate_id"),
        {"job_id": job_id, "candidate_id": candidate_id, "status": status}
    )
    db.commit()
    
    if status.upper() == 'CONTACTED':
        _send_whatsapp_to_candidate(db, job_id, candidate_id, target_phone)

def get_all_candidates(db: Session, user_id: UUID) -> list[dict]:
    # Fetch all candidates in the database (ensuring each is listed exactly once)
    # Only return candidates who are marked as INTERESTED or INTERVIEW_LINK_SENT
    rows = db.execute(
        select(Candidate, JobCandidate)
        .join(JobCandidate, JobCandidate.candidate_id == Candidate.id)
        .where(JobCandidate.recruitment_status.in_(['INTERESTED', 'INTERVIEW_LINK_SENT']))
        .order_by(Candidate.created_at.desc())
    ).all()
    
    # Extract unique candidates
    seen = set()
    candidates = []
    for cand, jc in rows:
        if cand.id not in seen:
            candidates.append(cand)
            seen.add(cand.id)
    
    results = []
    for candidate in candidates:
        # Get their most recent job application (if any) to populate job-specific fields
        jc_row = db.execute(
            select(JobCandidate, Job, ScreeningResult)
            .join(Job, Job.id == JobCandidate.job_id)
            .outerjoin(ScreeningResult, ScreeningResult.job_candidate_id == JobCandidate.id)
            .where(JobCandidate.candidate_id == candidate.id)
            .order_by(JobCandidate.created_at.desc())
            .limit(1)
        ).first()
        
        score = 0
        scoreLabel = "-"
        job_title = "-"
        stage = "-"
        job_id = None
        
        if jc_row:
            jc, job, screening = jc_row
            job_id = str(job.id)
            job_title = job.title
            stage = jc.recruitment_status
            if screening and screening.total_score:
                score = float(screening.total_score)
                lbl = str(screening.classification).replace("_", " ").title() if screening.classification else "-"
                if "Do Not Prioritize" in lbl:
                    scoreLabel = "Low Match"
                elif "Moderate" in lbl:
                    scoreLabel = "Moderate Match"
                elif "Strong" in lbl:
                    scoreLabel = "Strong Match"
                elif "Excellent" in lbl:
                    scoreLabel = "Excellent Match"
                else:
                    scoreLabel = lbl
                
        results.append({
            "id": str(candidate.id),
            "job_id": job_id,
            "name": candidate.name or "Unnamed",
            "email": candidate.email,
            "phone": candidate.phone,
            "location": candidate.location or "-",
            "exp": f"{candidate.total_experience_years} yrs" if candidate.total_experience_years else "-",
            "score": score,
            "scoreLabel": scoreLabel,
            "job": job_title,
            "skills": ", ".join([s.get("name") or s.get("skill") or s.get("skill_name") or str(s) if isinstance(s, dict) else str(s) for s in candidate.normalized_profile.get("skills", [])][:5]) if candidate.normalized_profile and candidate.normalized_profile.get("skills") else "-",
            "stage": stage,
            "experience_details": candidate.normalized_profile.get("experiences", []) if candidate.normalized_profile else [],
            "all_skills": candidate.normalized_profile.get("skills", []) if candidate.normalized_profile else []
        })
    return results

def get_outreach_campaigns(db: Session, user_id: UUID) -> dict:
    # Get jobs
    jobs = db.execute(select(Job).where(Job.created_by == user_id)).scalars().all()
    
    campaigns = []
    total_contacted = 0
    total_pending = 0
    total_interested = 0
    
    for job in jobs:
        rows = db.execute(
            select(JobCandidate, ScreeningResult)
            .join(ScreeningResult, ScreeningResult.job_candidate_id == JobCandidate.id)
            .where(JobCandidate.job_id == job.id)
        ).all()
        
        eligible = 0
        contacted = 0
        interested = 0
        
        for jc, screening in rows:
            if screening.total_score and screening.total_score >= 70:
                eligible += 1
                if jc.recruitment_status == 'CONTACTED':
                    contacted += 1
                elif jc.recruitment_status == 'INTERESTED':
                    interested += 1
                    contacted += 1 # interested implies contacted
        
        status = 'Active' if contacted > 0 else 'Draft'
        if eligible > 0 and contacted == eligible:
            status = 'Completed'
            
        campaigns.append({
            "id": str(job.id),
            "name": job.title,
            "job": job.title,
            "created": job.created_at.strftime("%b %d, %Y") if job.created_at else "",
            "rule": f"{eligible} eligible",
            "eligible": eligible,
            "contacted": contacted,
            "interested": interested,
            "status": status,
            "searchStr": f"{job.title} {status}".lower()
        })
        
        total_contacted += contacted
        total_pending += (eligible - contacted)
        total_interested += interested
        
    return {
        "metrics": {
            "contacted": total_contacted,
            "pending": total_pending,
            "interested": total_interested,
            "tests_assigned": 0
        },
        "campaigns": campaigns
    }
