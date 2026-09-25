# """All FastAPI routes in one file.

# Authentication is represented by X-User-Id/X-User-Role for this compact build.
# For development, job creation and screening can fall back to an active
# non-admin user when X-User-Id is not provided.

# In production, replace that development fallback with JWT/session
# authentication without changing the ownership queries.
# """

# from pathlib import Path
# from uuid import UUID

# from fastapi import (
#     APIRouter,
#     Depends,
#     File,
#     Form,
#     Header,
#     HTTPException,
#     UploadFile,
# )
# from sqlalchemy.orm import Session

# from .database import get_db
# from .models import User, Job
# from .tool_functions import (
#     ingest_resume_folder,
#     create_job,
#     screen_job,
#     get_user_jobs,
#     get_user_job_candidates,
#     get_admin_jobs,
#     get_admin_job_candidates,
#     read_file,
# )
# from .config import settings
# from fastapi.security import OAuth2PasswordRequestForm

# from .auth import (
#     hash_password,
#     verify_password,
#     create_access_token,
#     get_current_user,
#     require_admin,
# )

# router = APIRouter(prefix="/api")


# # ============================================================
# # AUTHENTICATION
# # ============================================================

# def current_user(
#     x_user_id: str = Header(..., alias="X-User-Id"),
#     db: Session = Depends(get_db),
# ) -> User:
#     """Return the authenticated active user."""

#     try:
#         user = db.get(User, UUID(x_user_id))
#     except ValueError:
#         user = None

#     if not user or not user.is_active:
#         raise HTTPException(
#             status_code=401,
#             detail="Invalid user",
#         )

#     return user


# def require_admin(
#     user: User = Depends(current_user),
# ) -> User:
#     """Return admin user or raise HTTP 403."""

#     if user.role != "ADMIN":
#         raise HTTPException(
#             status_code=403,
#             detail="Admin access required",
#         )

#     return user


# # ============================================================
# # RESUME INGESTION
# # ============================================================
# @router.post("/auth/register")
# def register(
#     name: str = Form(...),
#     email: str = Form(...),
#     password: str = Form(...),
#     db: Session = Depends(get_db),
# ):
#     existing = db.query(User).filter(
#         User.email == email
#     ).first()

#     if existing:
#         raise HTTPException(
#             status_code=400,
#             detail="Email already registered"
#         )

#     user = User(
#         name=name,
#         email=email,
#         password_hash=hash_password(password),
#         role="RECRUITER",
#         is_active=True,
#     )

#     db.add(user)
#     db.commit()
#     db.refresh(user)

#     return {
#         "message": "User registered successfully",
#         "user_id": str(user.id),
#         "name": user.name,
#         "email": user.email,
#         "role": user.role,
#     }

# @router.post("/auth/login")
# def login(
#     form_data: OAuth2PasswordRequestForm = Depends(),
#     db: Session = Depends(get_db),
# ):
#     user = db.query(User).filter(
#         User.email == form_data.username
#     ).first()

#     if not user or not verify_password(
#         form_data.password,
#         user.password_hash
#     ):
#         raise HTTPException(
#             status_code=401,
#             detail="Invalid email or password",
#         )

#     if not user.is_active:
#         raise HTTPException(
#             status_code=403,
#             detail="User account is inactive",
#         )

#     token = create_access_token(user)

#     return {
#         "access_token": token,
#         "token_type": "bearer",
#         "user": {
#             "id": str(user.id),
#             "name": user.name,
#             "email": user.email,
#             "role": user.role,
#         },
#     }

# @router.get("/auth/me")
# def me(
#     user: User = Depends(get_current_user),
# ):
#     return {
#         "id": str(user.id),
#         "name": user.name,
#         "email": user.email,
#         "role": user.role,
#         "is_active": user.is_active,
#     }
# @router.post("/resumes/ingest")
# def api_ingest_resumes(
#     db: Session = Depends(get_db),
# ):
#     """
#     Scan data/resumes and ingest all resumes.

#     Input:
#         None

#     Output:
#         Number of resumes processed.
#     """

#     return ingest_resume_folder(db)


# # ============================================================
# # CREATE JOB
# # ============================================================

# @router.post("/jobs")
# async def api_create_job(
#     x_user_id: str | None = Header(None, alias="X-User-Id"),
#     file: UploadFile | None = File(None),
#     jd_text: str | None = Form(None),
#     db: Session = Depends(get_db),
# ):
#     """
#     Create a Job from either:
#     - written JD text
#     - uploaded JD file

#     Exactly one input is required.

#     During development, if X-User-Id is not provided,
#     the first active non-admin user is used automatically.

#     Output:
#         Job information + AI extracted requirements.
#     """

#     # --------------------------------------------------------
#     # Resolve user
#     # --------------------------------------------------------

#     if x_user_id:
#         try:
#             user_id = UUID(x_user_id)
#         except ValueError:
#             raise HTTPException(
#                 status_code=401,
#                 detail="Invalid user ID",
#             )

#         user = (
#             db.query(User)
#             .filter(User.id == user_id)
#             .first()
#         )

#         if not user:
#             raise HTTPException(
#                 status_code=401,
#                 detail="User not found",
#             )

#     else:
#         # Development-only fallback.
#         # Uses an existing active non-admin user.
#         user = (
#             db.query(User)
#             .filter(
#                 User.is_active == True,
#                 User.role != "ADMIN",
#             )
#             .first()
#         )

#         if not user:
#             raise HTTPException(
#                 status_code=401,
#                 detail="No active non-admin user found for development.",
#             )

#         user_id = user.id

#     # --------------------------------------------------------
#     # Admin cannot create jobs
#     # --------------------------------------------------------

#     if user.role == "ADMIN":
#         raise HTTPException(
#             status_code=403,
#             detail="Admin cannot create job descriptions",
#         )

#     # --------------------------------------------------------
#     # Validate input
#     # --------------------------------------------------------

#     if file and jd_text:
#         raise HTTPException(
#             status_code=400,
#             detail="Provide either a JD file or JD text, not both",
#         )

#     if not file and not jd_text:
#         raise HTTPException(
#             status_code=400,
#             detail="Provide either a JD file or JD text",
#         )

#     try:

#         # ====================================================
#         # OPTION 1 — PASTED JOB DESCRIPTION
#         # ====================================================

#         if jd_text:

#             if not jd_text.strip():
#                 raise HTTPException(
#                     status_code=400,
#                     detail="Job description text cannot be empty",
#                 )

#             job = create_job(
#                 db=db,
#                 user_id=user_id,
#                 raw_text=jd_text.strip(),
#             )

#         # ====================================================
#         # OPTION 2 — UPLOADED JOB DESCRIPTION
#         # ====================================================

#         else:

#             # ------------------------------------------------
#             # Protect against unsafe filenames
#             # ------------------------------------------------

#             safe_filename = Path(
#                 file.filename or "job_description"
#             ).name

#             # ------------------------------------------------
#             # Make sure JD directory exists
#             # ------------------------------------------------

#             jd_directory = Path(settings.JD_DIR)

#             jd_directory.mkdir(
#                 parents=True,
#                 exist_ok=True,
#             )

#             # ------------------------------------------------
#             # Save uploaded file
#             # ------------------------------------------------

#             file_path = (
#                 jd_directory
#                 / safe_filename
#             )

#             contents = await file.read()

#             with open(
#                 file_path,
#                 "wb",
#             ) as f:
#                 f.write(contents)

#             # ------------------------------------------------
#             # Extract text from PDF/DOC/DOCX/TXT
#             # ------------------------------------------------

#             raw_text = read_file(
#                 str(file_path)
#             )

#             if not raw_text.strip():
#                 raise HTTPException(
#                     status_code=400,
#                     detail="Could not extract text from the uploaded JD",
#                 )

#             # ------------------------------------------------
#             # Create job + AI extraction
#             # ------------------------------------------------

#             job = create_job(
#                 db=db,
#                 user_id=user_id,
#                 raw_text=raw_text,
#                 file_name=safe_filename,
#                 file_path=str(file_path),
#             )

#         # ====================================================
#         # GET EXTRACTED REQUIREMENTS
#         # ====================================================

#         requirements = job.requirements

#         # ====================================================
#         # BUILD RESPONSE
#         # ====================================================

#         response = {
#             "job_id": str(job.id),

#             "title": job.title,

#             "description": job.description,

#             "location": job.location,

#             "work_mode": job.work_mode,

#             "status": job.status,

#             "requirements": {
#                 "job_title": (
#                     requirements.job_title
#                     if requirements
#                     else job.title
#                 ),

#                 "minimum_experience": (
#                     float(
#                         requirements.minimum_experience
#                     )
#                     if (
#                         requirements
#                         and requirements.minimum_experience
#                         is not None
#                     )
#                     else None
#                 ),

#                 "maximum_experience": (
#                     float(
#                         requirements.maximum_experience
#                     )
#                     if (
#                         requirements
#                         and requirements.maximum_experience
#                         is not None
#                     )
#                     else None
#                 ),

#                 "mandatory_skills": (
#                     requirements.mandatory_skills
#                     if requirements
#                     else []
#                 ),

#                 "preferred_skills": (
#                     requirements.preferred_skills
#                     if requirements
#                     else []
#                 ),

#                 "education": (
#                     requirements.education
#                     if requirements
#                     else []
#                 ),

#                 "certifications": (
#                     requirements.certifications
#                     if requirements
#                     else []
#                 ),

#                 "domains": (
#                     requirements.domains
#                     if requirements
#                     else []
#                 ),

#                 "responsibilities": (
#                     requirements.responsibilities
#                     if requirements
#                     else []
#                 ),

#                 "location": (
#                     requirements.location
#                     if requirements
#                     else job.location
#                 ),

#                 "work_mode": (
#                     requirements.work_mode
#                     if requirements
#                     else job.work_mode
#                 ),

#                 "notice_period_days": (
#                     requirements.notice_period_days
#                     if requirements
#                     else None
#                 ),

#                 "other_requirements": (
#                     requirements.other_requirements
#                     if requirements
#                     else []
#                 ),

#                 "confidence_score": (
#                     float(
#                         requirements.confidence_score
#                     )
#                     if (
#                         requirements
#                         and requirements.confidence_score
#                         is not None
#                     )
#                     else None
#                 ),
#             },
#         }

#         return response

#     except HTTPException:
#         raise

#     except Exception as exc:
#         db.rollback()

#         raise HTTPException(
#             status_code=500,
#             detail=f"Job creation failed: {str(exc)}",
#         )


# # ============================================================
# # SCREEN JOB
# # ============================================================

# @router.post("/jobs/{job_id}/screen")
# def api_screen_job(
#     job_id: UUID,
#     x_user_id: str | None = Header(None, alias="X-User-Id"),
#     db: Session = Depends(get_db),
# ):
#     """
#     Screen candidates for a specific job.

#     If X-User-Id is provided:
#         use that authenticated user. 

#     If X-User-Id is not provided:
#         use the first active non-admin user for development.

#     Users can screen only their own jobs.
#     Admins can screen any job.
#     """

#     # --------------------------------------------------------
#     # Resolve user
#     # --------------------------------------------------------

#     if x_user_id:

#         try:
#             user_id = UUID(x_user_id)

#         except ValueError:
#             raise HTTPException(
#                 status_code=401,
#                 detail="Invalid user ID",
#             )

#         user = (
#             db.query(User)
#             .filter(User.id == user_id)
#             .first()
#         )

#         if not user:
#             raise HTTPException(
#                 status_code=401,
#                 detail="User not found",
#             )

#     else:

#         # Development-only fallback.
#         user = (
#             db.query(User)
#             .filter(
#                 User.is_active == True,
#                 User.role != "ADMIN",
#             )
#             .first()
#         )

#         if not user:
#             raise HTTPException(
#                 status_code=401,
#                 detail="No active non-admin user found for development.",
#             )

#     # --------------------------------------------------------
#     # Find job
#     # --------------------------------------------------------

#     job = db.get(
#         Job,
#         job_id,
#     )

#     if not job:
#         raise HTTPException(
#             status_code=404,
#             detail="Job not found",
#         )

#     # --------------------------------------------------------
#     # Ownership check
#     # --------------------------------------------------------

#     if (
#         user.role != "ADMIN"
#         and job.created_by != user.id
#     ):
#         raise HTTPException(
#             status_code=403,
#             detail="Not your job",
#         )

#     # --------------------------------------------------------
#     # Run AI screening
#     # --------------------------------------------------------

#     try:

#         return screen_job(
#             db,
#             job_id,
#         )

#     except Exception as exc:

#         raise HTTPException(
#             status_code=500,
#             detail=str(exc),
#         )


# # ============================================================
# # USER JOBS
# # ============================================================

# @router.get("/user/jobs")
# def api_user_jobs(
#     user: User = Depends(get_current_user),
#     db: Session = Depends(get_db),
# ):
#     """
#     Return only jobs belonging to the authenticated user.
#     """

#     return get_user_jobs(
#         db,
#         user.id,
#     )


# # ============================================================
# # USER CANDIDATES 
# # ============================================================

# @router.get("/user/jobs/{job_id}/candidates")
# def api_user_candidates(
#     job_id: UUID,
#     user: User = Depends(current_user),
#     db: Session = Depends(get_db),
# ):
#     """
#     Return Top 10 candidates for the authenticated user's job.
#     """

#     try:

#         return get_user_job_candidates(
#             db,
#             user.id,
#             job_id,
#         )

#     except PermissionError:

#         raise HTTPException(
#             status_code=403,
#             detail="Not your job",
#         )


# # ============================================================
# # ADMIN JOBS
# # ============================================================

# @router.get("/admin/jobs")
# def api_admin_jobs(
#     admin: User = Depends(require_admin),
#     db: Session = Depends(get_db),
# ):
#     """
#     Return all jobs for administrators.
#     """

#     return get_admin_jobs(
#         db
#     )


# # ============================================================
# # ADMIN CANDIDATES
# # ============================================================

# @router.get("/admin/jobs/{job_id}/candidates")
# def api_admin_candidates(
#     job_id: UUID,
#     admin: User = Depends(require_admin),
#     db: Session = Depends(get_db),
# ):
#     """
#     Return Top 10 candidates for an admin-selected job.
#     """

#     try:

#         return get_admin_job_candidates(
#             db,
#             job_id,
#         )

#     except ValueError:

#         raise HTTPException(
#             status_code=404,
#             detail="Job not found",
#         )
"""FastAPI routes for NM-HireX.

Authentication:
    JWT Bearer authentication is used for all protected endpoints.

Roles:
    RECRUITER - can access only their own jobs/candidates/outreach.
    ADMIN     - can access all recruiter/job data and approve recruiters.

Recruiter approval:
    New recruiters are created with status=PENDING.
    Admin must approve them before they can log in.
"""


from .auth import require_admin
from pathlib import Path
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    Request,
)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import cast, String

from .database import get_db
from .models import User, Job, Candidate, JobCandidate, CandidateContact

from .tool_functions import (
    ingest_resume_folder,
    sync_google_drive,
    create_job,
    screen_job,
    get_user_jobs,
    get_user_job_candidates,
    get_admin_jobs,
    get_admin_job_candidates,
    read_file,
    get_user_dashboard,
    mark_candidate_contacted,
    get_all_candidates,
    get_outreach_candidates, update_candidate_status,
)

from .config import settings

from .auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_admin as auth_require_admin,
)


router = APIRouter(prefix="/api")


# ============================================================
# AUTHENTICATION
# ============================================================


@router.post("/auth/register")
def register(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Register a new recruiter.

    New recruiters are created as PENDING.
    Admin approval is required before login.
    """

    email = email.strip().lower()

    existing = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Email already registered",
        )

    # Basic password validation
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=400,
            detail="Password must not exceed 72 bytes",
        )

    user = User(
        name=name.strip(),
        email=email,
        password_hash=hash_password(password),
        role="RECRUITER",
        status="PENDING",
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "message": "Registration successful. Waiting for admin approval.",
        "user_id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "status": user.status,
    }


@router.post("/auth/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Login using email and password.

    OAuth2PasswordRequestForm uses:
        username = email
        password = password
    """

    email = form_data.username.strip().lower()

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    if not verify_password(
        form_data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is inactive",
        )

    # Recruiters must be approved by admin.
    if (
        user.role == "RECRUITER"
        and user.status != "APPROVED"
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Recruiter account is {user.status.lower()}. "
                "Please wait for admin approval."
            ),
        )

    token = create_access_token(user)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "status": user.status,
        },
    }

@router.post("/auth/login/recruiter")
def login_recruiter(
    name: str = Form(...),
    email: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    name = name.strip()
    
    user = db.query(User).filter(
        User.email == email,
        User.role == "RECRUITER"
    ).first()

    if not user or user.name.lower().strip() != name.lower():
        raise HTTPException(
            status_code=401,
            detail="Recruiter not found. Please register first.",
        )
        
    if getattr(user, 'status', 'APPROVED') == "PENDING":
        raise HTTPException(
            status_code=403,
            detail="Your account is pending admin approval."
        )
    elif getattr(user, 'status', 'APPROVED') == "REJECTED":
        raise HTTPException(
            status_code=403,
            detail="Your access has been rejected by the admin."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is inactive",
        )

    token = create_access_token(user)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": user.role,
        },
    }

@router.get("/auth/me")
def me(
    user: User = Depends(get_current_user),
):
    """Return the currently authenticated user."""

    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "status": user.status,
        "is_active": user.is_active,
    }


# ============================================================
# RECRUITER MANAGEMENT (ADMIN ONLY)
# ============================================================

@router.get("/admin/recruiters")
def api_get_recruiters(
    admin: User = Depends(auth_require_admin),
    db: Session = Depends(get_db),
):
    recruiters = db.query(User).filter(User.role == "RECRUITER").order_by(User.created_at.desc()).all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "email": r.email,
            "role": r.role,
            "status": getattr(r, 'status', 'PENDING'),
            "is_active": r.is_active,
            "created_at": r.created_at
        }
        for r in recruiters
    ]

@router.post("/admin/recruiters/{user_id}/approve")
def api_approve_recruiter(
    user_id: UUID,
    admin: User = Depends(auth_require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user or user.role != "RECRUITER":
        raise HTTPException(status_code=404, detail="Recruiter not found")
        
    user.status = "APPROVED"
    db.commit()
    
    return {
        "message": "Recruiter approved successfully",
        "user_id": str(user.id),
        "name": user.name,
        "email": user.email,
        "status": user.status
    }

@router.post("/admin/recruiters/{user_id}/reject")
def api_reject_recruiter(
    user_id: UUID,
    admin: User = Depends(auth_require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user or user.role != "RECRUITER":
        raise HTTPException(status_code=404, detail="Recruiter not found")
        
    user.status = "REJECTED"
    db.commit()
    
    return {
        "message": "Recruiter rejected",
        "user_id": str(user.id),
        "name": user.name,
        "email": user.email,
        "status": user.status
    }
class SyncRequest(BaseModel):
    source: str
    path_or_url: str

@router.post("/resumes/ingest")
def api_ingest_resumes(
    request: SyncRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Resume ingestion for recruiters and admins.
    Supports local folders or Google Drive URLs.
    """
    if request.source == "gdrive":
        return sync_google_drive(db, request.path_or_url)
    else:
        return ingest_resume_folder(db, custom_dir=request.path_or_url)


# ============================================================
# CREATE JOB
# ============================================================


@router.post("/jobs")
async def api_create_job(
    file: UploadFile | None = File(None),
    jd_text: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Job from either:

    1. Written JD text
    2. Uploaded JD file

    Recruiters can create jobs.
    Admins cannot create recruiter jobs.

    The job owner is taken from the JWT.
    """

    # --------------------------------------------------------
    # Only recruiters can create jobs
    # --------------------------------------------------------

    if user.role != "RECRUITER":
        raise HTTPException(
            status_code=403,
            detail="Only recruiters can create job descriptions",
        )

    if user.role == "RECRUITER" and user.status != "APPROVED":
        raise HTTPException(
            status_code=403,
            detail="Recruiter account is not approved",
        )

    user_id = user.id

    # --------------------------------------------------------
    # Validate input
    # --------------------------------------------------------

    if file and jd_text:
        raise HTTPException(
            status_code=400,
            detail="Provide either a JD file or JD text, not both",
        )

    if not file and not jd_text:
        raise HTTPException(
            status_code=400,
            detail="Provide either a JD file or JD text",
        )

    try:

        # ====================================================
        # OPTION 1 - PASTED JOB DESCRIPTION
        # ====================================================

        if jd_text:

            if not jd_text.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Job description text cannot be empty",
                )

            job = create_job(
                db=db,
                user_id=user_id,
                raw_text=jd_text.strip(),
            )

        # ====================================================
        # OPTION 2 - UPLOADED JOB DESCRIPTION
        # ====================================================

        else:

            safe_filename = Path(
                file.filename or "job_description"
            ).name

            jd_directory = Path(settings.JD_DIR)

            jd_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            file_path = jd_directory / safe_filename

            contents = await file.read()

            with open(
                file_path,
                "wb",
            ) as f:
                f.write(contents)

            raw_text = read_file(
                str(file_path)
            )

            if not raw_text.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Could not extract text from the uploaded JD",
                )

            job = create_job(
                db=db,
                user_id=user_id,
                raw_text=raw_text,
                file_name=safe_filename,
                file_path=str(file_path),
            )

        # ====================================================
        # GET EXTRACTED REQUIREMENTS
        # ====================================================

        requirements = job.requirements

        # ====================================================
        # BUILD RESPONSE
        # ====================================================

        return {
            "job_id": str(job.id),
            "created_by": str(job.created_by),
            "title": job.title,
            "description": job.description,
            "location": job.location,
            "work_mode": job.work_mode,
            "status": job.status,

            "requirements": {
                "job_title": (
                    requirements.job_title
                    if requirements
                    else job.title
                ),

                "minimum_experience": (
                    float(requirements.minimum_experience)
                    if (
                        requirements
                        and requirements.minimum_experience is not None
                    )
                    else None
                ),

                "maximum_experience": (
                    float(requirements.maximum_experience)
                    if (
                        requirements
                        and requirements.maximum_experience is not None
                    )
                    else None
                ),

                "mandatory_skills": (
                    requirements.mandatory_skills
                    if requirements
                    else []
                ),

                "preferred_skills": (
                    requirements.preferred_skills
                    if requirements
                    else []
                ),

                "education": (
                    requirements.education
                    if requirements
                    else []
                ),

                "certifications": (
                    requirements.certifications
                    if requirements
                    else []
                ),

                "domains": (
                    requirements.domains
                    if requirements
                    else []
                ),

                "responsibilities": (
                    requirements.responsibilities
                    if requirements
                    else []
                ),

                "location": (
                    requirements.location
                    if requirements
                    else job.location
                ),

                "work_mode": (
                    requirements.work_mode
                    if requirements
                    else job.work_mode
                ),

                "notice_period_days": (
                    requirements.notice_period_days
                    if requirements
                    else None
                ),

                "other_requirements": (
                    requirements.other_requirements
                    if requirements
                    else []
                ),

                "confidence_score": (
                    float(requirements.confidence_score)
                    if (
                        requirements
                        and requirements.confidence_score is not None
                    )
                    else None
                ),
            },
        }

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Job creation failed: {str(exc)}",
        )


# ============================================================
# SCREEN JOB
# ============================================================


@router.post("/jobs/{job_id}/screen")
def api_screen_job(
    job_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Screen candidates for a job.

    Recruiter:
        Can screen only their own jobs.

    Admin:
        Can technically screen any job through this endpoint,
        although the Admin UI should not expose Match Agent.
    """

    job = db.get(
        Job,
        job_id,
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    # --------------------------------------------------------
    # Ownership check
    # --------------------------------------------------------

    if (
        user.role != "ADMIN"
        and job.created_by != user.id
    ):
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this job",
        )

    # --------------------------------------------------------
    # Recruiter approval
    # --------------------------------------------------------

    if (
        user.role == "RECRUITER"
        and user.status != "APPROVED"
    ):
        raise HTTPException(
            status_code=403,
            detail="Recruiter account is not approved",
        )

    # --------------------------------------------------------
    # Run AI screening
    # --------------------------------------------------------

    try:

        return screen_job(
            db,
            job_id,
        )

    except Exception as exc:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# RECRUITER - DASHBOARD
# ============================================================


@router.get("/user/dashboard")
def api_user_dashboard(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return dashboard stats and pipeline for the recruiter.
    """

    if user.role not in ["RECRUITER", "ADMIN"]:
        raise HTTPException(
            status_code=403,
            detail="Recruiter access required",
        )

    if user.role == "RECRUITER" and user.status != "APPROVED":
        raise HTTPException(
            status_code=403,
            detail="Recruiter account is not approved",
        )

    return get_user_dashboard(
        db,
        user.id,
    )


# ============================================================
# RECRUITER - OWN JOBS
# ============================================================


@router.get("/user/jobs")
def api_user_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return only jobs belonging to the authenticated recruiter.
    """

    if user.role not in ["RECRUITER", "ADMIN"]:
        raise HTTPException(
            status_code=403,
            detail="Recruiter access required",
        )

    if user.role == "RECRUITER" and user.status != "APPROVED":
        raise HTTPException(
            status_code=403,
            detail="Recruiter account is not approved",
        )

    return get_user_jobs(
        db,
        user.id,
    )


# ============================================================
# RECRUITER - OWN JOB CANDIDATES
# ============================================================


@router.get("/user/jobs/{job_id}/candidates")
def api_user_candidates(
    job_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return candidates matched to the authenticated recruiter's job.

    Ownership is checked by user ID.
    """

    if user.role not in ["RECRUITER", "ADMIN"]:
        raise HTTPException(
            status_code=403,
            detail="Recruiter access required",
        )

    if user.role == "RECRUITER" and user.status != "APPROVED":
        raise HTTPException(
            status_code=403,
            detail="Recruiter account is not approved",
        )

    try:

        return get_user_job_candidates(
            db,
            user.id,
            job_id,
        )

    except PermissionError:

        raise HTTPException(
            status_code=403,
            detail="You do not have access to this job",
        )


# ============================================================
# ADMIN - ALL JOBS
# ============================================================


@router.get("/admin/jobs")
def api_admin_jobs(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Return all recruiter jobs for administrators.
    """

    return get_admin_jobs(
        db
    )


# ============================================================
# ADMIN - JOB CANDIDATES
# ============================================================


@router.get("/admin/jobs/{job_id}/candidates")
def api_admin_candidates(
    job_id: UUID,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Return candidates matched to an admin-selected job.
    """

    try:

        return get_admin_job_candidates(
            db,
            job_id,
        )

    except ValueError:

        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

@router.post("/user/jobs/{job_id}/candidates/{candidate_id}/contact")
def api_mark_contacted(
    job_id: UUID,
    candidate_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    mark_candidate_contacted(db, job_id, candidate_id)
    return {"status": "success"}

@router.get("/user/candidates")
def api_get_all_candidates(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_all_candidates(db, user.id)

@router.get("/user/outreach")
def api_get_outreach(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_outreach_candidates(db, user.id)


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    try:
        payload = await request.json()

        print("========================================")
        print("INCOMING WHATSAPP WEBHOOK")
        print(payload)
        print("========================================")

        data = payload.get("data", {})

        # Only process incoming candidate messages
        event = payload.get("event")

        if event != "whatsapp.message.received":
            print(f"Ignoring WhatsApp event: {event}")

            return {
                "success": True,
                "message": "Event received but not a candidate message"
            }

        # Get candidate's reply
        response_text = None

        if isinstance(data.get("text"), dict):
            response_text = data["text"].get("body")

        if not response_text:
            response_text = data.get("body")

        if not response_text:
            response_text = payload.get("text")

        if not response_text:
            response_text = payload.get("body")

        reference_id = data.get("referenceId")
        message_id = data.get("messageId")

        print("Reference ID:", reference_id)
        print("Message ID:", message_id)
        print("Candidate Response:", response_text)

        if not reference_id:
            return {
                "success": False,
                "message": "referenceId missing"
            }

        if not response_text:
            return {
                "success": False,
                "message": "Response text missing"
            }

        # referenceId format:
        # NMHireX-<first 8 characters of candidate UUID>
        candidate_prefix = reference_id.replace(
            "NMHireX-", "",
            1
        )

        # Find candidate
        candidate = (
            db.query(Candidate)
            .filter(
                cast(Candidate.id, String).like(
                    f"{candidate_prefix}%"
                )
            )
            .first()
        )

        if not candidate:
            print(
                "Candidate not found for reference:",
                reference_id
            )

            return {
                "success": False,
                "message": "Candidate not found"
            }

        print("Candidate found:", candidate.id)
        print("Candidate name:", candidate.name)

        # Find previous WhatsApp message
        outbound_contact = (
            db.query(CandidateContact)
            .join(
                JobCandidate,
                JobCandidate.id ==
                CandidateContact.job_candidate_id
            )
            .filter(
                JobCandidate.candidate_id == candidate.id,
                CandidateContact.channel == "WHATSAPP",
                CandidateContact.message_type == "OUTBOUND"
            )
            .order_by(
                CandidateContact.created_at.desc()
            )
            .first()
        )

        if not outbound_contact:
            return {
                "success": False,
                "message": "Outbound WhatsApp contact not found"
            }

        # Save candidate response
        inbound_contact = CandidateContact(
            job_candidate_id=outbound_contact.job_candidate_id,
            channel="WHATSAPP",
            message_type="INBOUND",
            message=response_text,
            provider="NMVE",
            external_message_id=message_id,
            status="RECEIVED",
            responded_at=datetime.utcnow(),
            response_text=response_text,
        )

        db.add(inbound_contact)
        db.commit()
        db.refresh(inbound_contact)

        print("========================================")
        print("WHATSAPP RESPONSE SAVED TO DATABASE")
        print("Candidate:", candidate.name)
        print("Response:", response_text)
        print("Contact ID:", inbound_contact.id)
        print("========================================")

        # --- Intent Detection via OpenAI ---
        intent = "NEUTRAL"
        try:
            import openai
            openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

            completion = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a recruitment assistant analyzing a candidate's WhatsApp reply to a job opportunity message. "
                            "Classify the candidate's response intent as exactly one of: POSITIVE, NEGATIVE, or NEUTRAL.\n\n"
                            "POSITIVE: candidate is interested, wants to proceed, open to discussing, asking for details, or any affirmative response.\n"
                            "NEGATIVE: candidate is not interested, declines, asks to stop contact, is unavailable, or any rejection.\n"
                            "NEUTRAL: unclear, irrelevant, or ambiguous response.\n\n"
                            "Reply with ONLY one word: POSITIVE, NEGATIVE, or NEUTRAL."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Candidate reply: {response_text}"
                    }
                ],
                max_tokens=10,
                temperature=0
            )

            raw_intent = completion.choices[0].message.content.strip().upper()
            if raw_intent in ("POSITIVE", "NEGATIVE", "NEUTRAL"):
                intent = raw_intent

        except Exception as ai_err:
            print(f"OpenAI intent detection failed, falling back to keyword: {ai_err}")
            # Keyword fallback
            lower = response_text.lower()
            positive_words = ["yes", "interested", "sure", "okay", "ok", "please", "would like", "open", "available", "happy to", "love to", "definitely", "absolutely", "great", "sounds good"]
            negative_words = ["no", "not interested", "decline", "stop", "don't contact", "unsubscribe", "not looking", "busy", "cannot", "can't", "won't", "no thanks", "nope"]
            if any(w in lower for w in negative_words):
                intent = "NEGATIVE"
            elif any(w in lower for w in positive_words):
                intent = "POSITIVE"

        print(f"Detected intent: {intent}")

        # Save intent to inbound_contact
        inbound_contact.response_intent = intent
        db.commit()

        # Update job_candidate status and send auto-reply
        job_candidate_rec = db.query(JobCandidate).filter(
            JobCandidate.id == outbound_contact.job_candidate_id
        ).first()

        if job_candidate_rec:
            from sqlalchemy import text as sql_text
            from .tool_functions import _send_whatsapp_text_message

            current_status = job_candidate_rec.recruitment_status

            if intent == "POSITIVE" and current_status == "CONTACTED":
                # Step 1 – Mark as INTERESTED and ask candidate to pick a time slot
                db.execute(
                    sql_text("UPDATE job_candidates SET recruitment_status = 'INTERESTED', updated_at = now() WHERE id = :id"),
                    {"id": job_candidate_rec.id}
                )
                db.commit()

                # Build the next 7 days with options
                from datetime import timedelta, timezone as tz
                now_ist = datetime.now(tz.utc) + timedelta(hours=5, minutes=30)
                day_lines = []
                for i in range(1, 8):
                    day = now_ist + timedelta(days=i)
                    day_lines.append(f"  {i}. {day.strftime('%A, %d %B %Y')} – 10:00 AM / 2:00 PM / 4:00 PM")
                slot_list = "\n".join(day_lines)

                calendar_msg = (
                    f"Great news! 🎉 We'd love to move forward with your application.\n\n"
                    f"Please select a convenient date and time for your interview from the options below "
                    f"(within the next 7 days):\n\n"
                    f"{slot_list}\n\n"
                    f"Simply reply with the *day number and time*, for example:\n"
                    f"  \"3, 2:00 PM\" or \"Tuesday 10:00 AM\"\n\n"
                    f"We look forward to connecting with you! 😊"
                )
                _send_whatsapp_text_message(candidate.phone, calendar_msg)

                # Save the outbound calendar message in candidate_contacts
                outbound_cal = CandidateContact(
                    job_candidate_id=job_candidate_rec.id,
                    channel="WHATSAPP",
                    message_type="OUTBOUND",
                    message=calendar_msg,
                    provider="NMVE",
                    status="SENT",
                    sent_at=datetime.utcnow(),
                )
                db.add(outbound_cal)
                db.commit()
                print(f"Sent interview slot selection message to {candidate.name}")

            elif current_status == "INTERESTED":
                # Step 2 – Candidate is replying with their chosen time slot.
                # Parse the date/time using OpenAI.
                from datetime import timedelta, timezone as tz
                now_ist = datetime.now(tz.utc) + timedelta(hours=5, minutes=30)
                scheduled_at = None
                try:
                    import openai as _openai
                    _client = _openai.OpenAI(api_key=settings.OPENAI_API_KEY)
                    parse_completion = _client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    f"Today is {now_ist.strftime('%A, %d %B %Y')}. "
                                    "A job candidate has replied with their preferred interview date and time. "
                                    "Extract the date and time from their message and return it as an ISO 8601 string "
                                    "(YYYY-MM-DDTHH:MM:SS+05:30). If you cannot determine a valid date/time, reply with 'UNKNOWN'."
                                )
                            },
                            {
                                "role": "user",
                                "content": f"Candidate reply: {response_text}"
                            }
                        ],
                        max_tokens=30,
                        temperature=0
                    )
                    parsed_str = parse_completion.choices[0].message.content.strip()
                    print(f"Parsed datetime string: {parsed_str}")
                    if parsed_str.upper() != "UNKNOWN":
                        from datetime import datetime as dt
                        try:
                            scheduled_at = dt.fromisoformat(parsed_str)
                        except ValueError:
                            scheduled_at = None
                except Exception as parse_err:
                    print(f"Date/time parse error: {parse_err}")

                if scheduled_at is None:
                    # Could not parse – ask again
                    retry_msg = (
                        "Sorry, I couldn't understand the date and time you selected. "
                        "Please reply in this format, e.g.: \"Monday, 10:00 AM\" or \"27 September, 2:00 PM\"."
                    )
                    _send_whatsapp_text_message(candidate.phone, retry_msg)
                    print(f"Could not parse time from '{response_text}' – asked candidate to retry")
                else:
                    # Persist the scheduled time and a Teams link in job_candidates
                    teams_link = "https://teams.microsoft.com/l/meetup-join/interview"
                    db.execute(
                        sql_text(
                            "UPDATE job_candidates "
                            "SET recruitment_status = 'INTERVIEW_LINK_SENT', "
                            "    interview_scheduled_at = :scheduled_at, "
                            "    interview_link = :teams_link, "
                            "    updated_at = now() "
                            "WHERE id = :id"
                        ),
                        {
                            "id": job_candidate_rec.id,
                            "scheduled_at": scheduled_at,
                            "teams_link": teams_link,
                        }
                    )
                    db.commit()

                    formatted_time = scheduled_at.strftime("%A, %d %B %Y at %I:%M %p IST")
                    interview_msg = (
                        f"Thank you for confirming! ✅\n\n"
                        f"Your interview has been scheduled for:\n"
                        f"📅 *{formatted_time}*\n\n"
                        f"Here is your Microsoft Teams link to join the interview:\n"
                        f"🔗 {teams_link}\n\n"
                        f"This link will allow you to open and give your exam on {formatted_time}.\n\n"
                        f"Please join the meeting 5 minutes early. We look forward to speaking with you! 🙂"
                    )
                    _send_whatsapp_text_message(candidate.phone, interview_msg)

                    # Persist the outbound interview message in candidate_contacts
                    outbound_interview = CandidateContact(
                        job_candidate_id=job_candidate_rec.id,
                        channel="WHATSAPP",
                        message_type="OUTBOUND",
                        message=interview_msg,
                        provider="NMVE",
                        status="SENT",
                        sent_at=datetime.utcnow(),
                    )
                    db.add(outbound_interview)
                    db.commit()
                    print(f"Sent Teams interview link to {candidate.name} for {formatted_time}")

            elif intent == "NEGATIVE" and current_status not in ("INTERVIEW_LINK_SENT", "NOT_INTERESTED"):
                # Mark as NOT_INTERESTED
                db.execute(
                    sql_text("UPDATE job_candidates SET recruitment_status = 'NOT_INTERESTED', updated_at = now() WHERE id = :id"),
                    {"id": job_candidate_rec.id}
                )
                db.commit()

                # Send thank you message
                thank_you_msg = "Thank you for your response. We wish you all the best in your career journey! 🙏"
                _send_whatsapp_text_message(candidate.phone, thank_you_msg)
                print(f"Sent thank-you to {candidate.name}")


        return {
            "success": True,
            "message": "WhatsApp response received and processed",
            "contact_id": str(inbound_contact.id),
            "intent": intent
        }

    except Exception as e:
        db.rollback()

        print("========================================")
        print("WHATSAPP WEBHOOK ERROR")
        print(str(e))
        print("========================================")

        return {
            "success": False,
            "message": "Failed to process WhatsApp webhook",
            "error": str(e)
        }


class StatusUpdateRequest(BaseModel):
    status: str
    target_phone: str | None = None
@router.post("/user/jobs/{job_id}/candidates/{candidate_id}/status")
def api_update_candidate_status(
    job_id: UUID,
    candidate_id: UUID,
    req: StatusUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role == "RECRUITER" and user.status != "APPROVED":
        raise HTTPException(status_code=403, detail="Recruiter account is not approved")
        
    update_candidate_status(db, job_id, candidate_id, req.status, req.target_phone)
    return {"message": "Status updated successfully"}
