import json
import os
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField, Session, SQLModel, create_engine, or_, select

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aiplay.db")

app = FastAPI(title="智能刷题平台 API", version="0.2.0")
engine = create_engine(DATABASE_URL, echo=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


class ReviewStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ImportStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    review = "review"
    done = "done"
    failed = "failed"


class User(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    username: str = SQLField(index=True, unique=True)
    full_name: Optional[str] = None
    role: str = SQLField(default="student", index=True)
    hashed_password: str


class Question(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    type: str = SQLField(default="single_choice", index=True)
    title: str
    options: str = "[]"
    answer: str
    analysis: str = ""
    difficulty: int = SQLField(default=3, ge=1, le=5)
    subject: str = ""
    chapter: str = ""
    knowledge_points: str = "[]"
    tags: str = "[]"
    source: str = "manual"
    review_status: ReviewStatus = SQLField(default=ReviewStatus.pending, index=True)
    created_by: str
    created_at: datetime = SQLField(default_factory=datetime.utcnow)


class ImportTask(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    filename: str
    file_type: str
    status: ImportStatus = SQLField(default=ImportStatus.queued, index=True)
    parsed_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    error_message: str = ""
    created_by: str
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow)


class WrongQuestion(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    user_id: int = SQLField(index=True)
    question_id: int = SQLField(index=True)
    wrong_count: int = 1
    first_wrong_at: datetime = SQLField(default_factory=datetime.utcnow)
    last_practiced_at: datetime = SQLField(default_factory=datetime.utcnow)
    mastered: bool = False




class ExamRecord(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    user_id: int = SQLField(index=True)
    mode: str = SQLField(default="practice", index=True)
    subject: str = ""
    total_questions: int = 0
    correct_count: int = 0
    started_at: datetime = SQLField(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class UserAnswer(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    exam_id: int = SQLField(index=True)
    user_id: int = SQLField(index=True)
    question_id: int = SQLField(index=True)
    user_answer: str
    is_correct: bool
    answered_at: datetime = SQLField(default_factory=datetime.utcnow)


class UserCreate(BaseModel):
    username: str
    password: str = Field(min_length=6)
    full_name: Optional[str] = None
    role: str = "student"


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class QuestionIn(BaseModel):
    type: str = "single_choice"
    title: str
    options: List[str] = []
    answer: str
    analysis: str = ""
    difficulty: int = Field(default=3, ge=1, le=5)
    subject: str = ""
    chapter: str = ""
    knowledge_points: List[str] = []
    tags: List[str] = []
    source: str = "manual"


class QuestionOut(BaseModel):
    id: int
    type: str
    title: str
    options: List[str]
    answer: str
    analysis: str
    difficulty: int
    subject: str
    chapter: str
    knowledge_points: List[str]
    tags: List[str]
    source: str
    review_status: ReviewStatus
    created_by: str
    created_at: datetime




class ExamStartIn(BaseModel):
    mode: str = "practice"
    subject: str = ""
    limit: int = Field(default=10, ge=1, le=100)


class AnswerIn(BaseModel):
    question_id: int
    user_answer: str


class ImportTaskIn(BaseModel):
    filename: str
    file_type: str = Field(pattern="^(docx|doc|md|xlsx|xls|pdf|image)$")


class ImportTaskUpdate(BaseModel):
    status: ImportStatus
    parsed_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    error_message: str = ""


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_session():
    with Session(engine) as session:
        yield session


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise credentials_exception
    return user


def require_roles(*roles: str):
    def checker(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return checker


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat(), "version": app.version}


@app.post("/auth/register", response_model=dict)
def register(payload: UserCreate, session: Session = Depends(get_session)):
    existing = session.exec(select(User).where(User.username == payload.username)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(
        username=payload.username,
        full_name=payload.full_name,
        role=payload.role,
        hashed_password=get_password_hash(payload.password),
    )
    session.add(user)
    session.commit()
    return {"message": "registered"}


@app.post("/auth/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=access_token)


@app.post("/questions", response_model=QuestionOut)
def create_question(
    payload: QuestionIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin", "researcher", "teacher")),
):
    question = Question(
        **payload.model_dump(exclude={"options", "knowledge_points", "tags"}),
        options=json.dumps(payload.options, ensure_ascii=False),
        knowledge_points=json.dumps(payload.knowledge_points, ensure_ascii=False),
        tags=json.dumps(payload.tags, ensure_ascii=False),
        created_by=user.username,
    )
    session.add(question)
    session.commit()
    session.refresh(question)
    return _to_question_out(question)


@app.patch("/questions/{question_id}/review", response_model=QuestionOut)
def review_question(
    question_id: int,
    review_status: ReviewStatus,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("admin", "researcher")),
):
    row = session.get(Question, question_id)
    if not row:
        raise HTTPException(status_code=404, detail="Question not found")
    row.review_status = review_status
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_question_out(row)


@app.get("/questions", response_model=List[QuestionOut])
def list_questions(
    subject: Optional[str] = None,
    qtype: Optional[str] = None,
    review_status: Optional[ReviewStatus] = None,
    keyword: Optional[str] = Query(default=None, min_length=1),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    query = select(Question)
    if subject:
        query = query.where(Question.subject == subject)
    if qtype:
        query = query.where(Question.type == qtype)
    if review_status:
        query = query.where(Question.review_status == review_status)
    if keyword:
        query = query.where(or_(Question.title.contains(keyword), Question.tags.contains(keyword)))
    rows = session.exec(query.order_by(Question.id.desc())).all()
    return [_to_question_out(r) for r in rows]


@app.post("/question-import/tasks")
def create_import_task(
    payload: ImportTaskIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin", "researcher", "teacher")),
):
    task = ImportTask(filename=payload.filename, file_type=payload.file_type, created_by=user.username)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@app.patch("/question-import/tasks/{task_id}")
def update_import_task(
    task_id: int,
    payload: ImportTaskUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("admin", "researcher")),
):
    task = session.get(ImportTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for key, value in payload.model_dump().items():
        setattr(task, key, value)
    task.updated_at = datetime.utcnow()
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@app.get("/question-import/tasks")
def list_import_tasks(session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    return session.exec(select(ImportTask).order_by(ImportTask.id.desc())).all()


@app.post("/wrong-questions/{question_id}")
def mark_wrong(question_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    existing = session.exec(
        select(WrongQuestion).where(
            WrongQuestion.user_id == user.id,
            WrongQuestion.question_id == question_id,
        )
    ).first()
    if existing:
        existing.wrong_count += 1
        existing.last_practiced_at = datetime.utcnow()
        existing.mastered = False
        session.add(existing)
    else:
        session.add(WrongQuestion(user_id=user.id, question_id=question_id))
    session.commit()
    return {"message": "recorded"}


@app.patch("/wrong-questions/{question_id}/mastered")
def mark_mastered(question_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    row = session.exec(
        select(WrongQuestion).where(
            WrongQuestion.user_id == user.id,
            WrongQuestion.question_id == question_id,
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Wrong question record not found")
    row.mastered = True
    row.last_practiced_at = datetime.utcnow()
    session.add(row)
    session.commit()
    return {"message": "mastered"}


@app.get("/wrong-questions")
def list_wrong_questions(mastered: Optional[bool] = None, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    query = select(WrongQuestion).where(WrongQuestion.user_id == user.id)
    if mastered is not None:
        query = query.where(WrongQuestion.mastered == mastered)
    return session.exec(query.order_by(WrongQuestion.last_practiced_at.desc())).all()


@app.get("/statistics/overview")
def stats_overview(session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    total_questions = len(session.exec(select(Question)).all())
    total_users = len(session.exec(select(User)).all())
    total_wrong_records = len(session.exec(select(WrongQuestion)).all())
    pending_review = len(session.exec(select(Question).where(Question.review_status == ReviewStatus.pending)).all())
    return {
        "total_questions": total_questions,
        "total_users": total_users,
        "total_wrong_records": total_wrong_records,
        "pending_review": pending_review,
    }


def _to_question_out(row: Question) -> QuestionOut:
    return QuestionOut(
        id=row.id,
        type=row.type,
        title=row.title,
        options=json.loads(row.options or "[]"),
        answer=row.answer,
        analysis=row.analysis,
        difficulty=row.difficulty,
        subject=row.subject,
        chapter=row.chapter,
        knowledge_points=json.loads(row.knowledge_points or "[]"),
        tags=json.loads(row.tags or "[]"),
        source=row.source,
        review_status=row.review_status,
        created_by=row.created_by,
        created_at=row.created_at,
    )


@app.post("/exams/start")
def start_exam(payload: ExamStartIn, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    query = select(Question).where(Question.review_status == ReviewStatus.approved)
    if payload.subject:
        query = query.where(Question.subject == payload.subject)
    questions = session.exec(query.limit(payload.limit)).all()
    exam = ExamRecord(user_id=user.id, mode=payload.mode, subject=payload.subject, total_questions=len(questions))
    session.add(exam)
    session.commit()
    session.refresh(exam)
    return {
        "exam_id": exam.id,
        "questions": [_to_question_out(q) for q in questions],
    }


@app.post("/exams/{exam_id}/answer")
def submit_answer(exam_id: int, payload: AnswerIn, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    exam = session.get(ExamRecord, exam_id)
    if not exam or exam.user_id != user.id:
        raise HTTPException(status_code=404, detail="Exam not found")
    question = session.get(Question, payload.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    is_correct = payload.user_answer.strip() == question.answer.strip()
    session.add(
        UserAnswer(
            exam_id=exam.id,
            user_id=user.id,
            question_id=payload.question_id,
            user_answer=payload.user_answer,
            is_correct=is_correct,
        )
    )
    if is_correct:
        exam.correct_count += 1
    else:
        existing = session.exec(
            select(WrongQuestion).where(WrongQuestion.user_id == user.id, WrongQuestion.question_id == question.id)
        ).first()
        if existing:
            existing.wrong_count += 1
            existing.last_practiced_at = datetime.utcnow()
            existing.mastered = False
            session.add(existing)
        else:
            session.add(WrongQuestion(user_id=user.id, question_id=question.id))
    session.add(exam)
    session.commit()
    return {"is_correct": is_correct, "correct_answer": question.answer}


@app.post("/exams/{exam_id}/complete")
def complete_exam(exam_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    exam = session.get(ExamRecord, exam_id)
    if not exam or exam.user_id != user.id:
        raise HTTPException(status_code=404, detail="Exam not found")
    exam.completed_at = datetime.utcnow()
    session.add(exam)
    session.commit()
    accuracy = (exam.correct_count / exam.total_questions) if exam.total_questions else 0
    return {
        "exam_id": exam.id,
        "total_questions": exam.total_questions,
        "correct_count": exam.correct_count,
        "accuracy": round(accuracy, 4),
        "completed_at": exam.completed_at,
    }


@app.get("/exams/history")
def exam_history(session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    exams = session.exec(select(ExamRecord).where(ExamRecord.user_id == user.id).order_by(ExamRecord.id.desc())).all()
    return exams
