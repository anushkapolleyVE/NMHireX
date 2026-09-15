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

from pydantic import BaseModel
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .database import get_db
from .models import User, Job

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
    user = db.query(User).filter(
        User.email == email,
        User.role == "RECRUITER"
    ).first()

    if not user or user.name.lower() != name.lower():
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
    admin: User = Depends(auth_require_admin),
    db: Session = Depends(get_db),
):
    """
    Admin-only resume ingestion.
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

    if user.status != "APPROVED":
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

    if user.role != "RECRUITER":
        raise HTTPException(
            status_code=403,
            detail="Recruiter access required",
        )

    if user.status != "APPROVED":
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

    if user.role != "RECRUITER":
        raise HTTPException(
            status_code=403,
            detail="Recruiter access required",
        )

    if user.status != "APPROVED":
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