"""Test generation and HTTPX execution API."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import TEST_MAX_CASES_PER_RUN
from app.database.connection import get_db
from app.database.models import ApiSpecification, Project, TestCase, TestResult, TestRun, User
from app.schemas.testing import (
    SelectedTestRunRequest,
    TestCaseOut,
    TestCasePatch,
    TestResultOut,
    TestRunOut,
    TestRunRequest,
)
from app.services.test_executor import TestExecutionConfigurationError, execute_test_run
from app.services.test_generator import generate_test_cases
from app.services.authentication import get_current_user
from app.services.authorization import READ_ROLES, WRITE_ROLES, project_membership

router = APIRouter(tags=["automated testing"])


def _case(case: TestCase) -> TestCaseOut:
    return TestCaseOut.model_validate(case)


def _authorized_specification(
    db: Session,
    user: User,
    specification_id: UUID,
    *,
    write: bool = False,
) -> ApiSpecification:
    specification = db.get(ApiSpecification, specification_id)
    if not specification:
        raise HTTPException(404, "Specification not found.")
    project, _ = project_membership(
        db,
        user,
        specification.project_id,
        WRITE_ROLES if write else READ_ROLES,
    )
    if write and project.is_archived:
        raise HTTPException(409, "Restore this project before changing its tests.")
    return specification


def _authorized_case(
    db: Session,
    user: User,
    test_case_id: UUID,
    *,
    write: bool = False,
) -> TestCase:
    case = db.get(TestCase, test_case_id)
    if not case:
        raise HTTPException(404, "Test case not found.")
    _authorized_specification(db, user, case.specification_id, write=write)
    return case


def _authorized_run(
    db: Session,
    user: User,
    test_run_id: UUID,
    *,
    write: bool = False,
) -> TestRun:
    run = db.get(TestRun, test_run_id)
    if not run:
        raise HTTPException(404, "Test run not found.")
    _authorized_specification(db, user, run.specification_id, write=write)
    return run


def _execute(db: Session, specification: ApiSpecification, cases: list[TestCase], payload: TestRunRequest) -> TestRun:
    if len(cases) > TEST_MAX_CASES_PER_RUN:
        raise HTTPException(422, f"A run is limited to {TEST_MAX_CASES_PER_RUN} test cases.")
    try:
        return execute_test_run(
            db,
            specification=specification,
            cases=cases,
            base_url=payload.base_url,
            environment_name=payload.environment_name,
            timeout_seconds=payload.timeout_seconds,
            include_negative_tests=payload.include_negative_tests,
            allow_write_operations=payload.allow_write_operations,
            confirm_destructive=payload.confirm_destructive,
            default_headers=payload.default_headers,
        )
    except TestExecutionConfigurationError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc


@router.post("/api/v1/specifications/{specification_id}/test-cases/generate")
def generate_cases(
    specification_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    specification = _authorized_specification(db, user, specification_id, write=True)
    try:
        generated = generate_test_cases(db, specification_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    cases = db.query(TestCase).filter(TestCase.specification_id == specification_id).order_by(TestCase.created_at, TestCase.name).all()
    return {"created_count": len(generated), "total_count": len(cases), "test_cases": [_case(item).model_dump(mode="json") for item in cases]}


@router.get("/api/v1/specifications/{specification_id}/test-cases", response_model=list[TestCaseOut])
def list_test_cases(
    specification_id: UUID,
    include_disabled: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TestCaseOut]:
    _authorized_specification(db, user, specification_id)
    query = db.query(TestCase).filter(TestCase.specification_id == specification_id)
    if not include_disabled:
        query = query.filter(TestCase.is_enabled.is_(True))
    return [_case(item) for item in query.order_by(TestCase.created_at, TestCase.name).all()]


@router.get("/api/v1/test-cases/{test_case_id}", response_model=TestCaseOut)
def get_test_case(
    test_case_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestCaseOut:
    case = _authorized_case(db, user, test_case_id)
    return _case(case)


@router.patch("/api/v1/test-cases/{test_case_id}", response_model=TestCaseOut)
def update_test_case(
    test_case_id: UUID,
    payload: TestCasePatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestCaseOut:
    case = _authorized_case(db, user, test_case_id, write=True)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        if value is not None:
            setattr(case, key, value)
    db.commit()
    db.refresh(case)
    return _case(case)


@router.delete("/api/v1/test-cases/{test_case_id}", status_code=204)
def delete_test_case(
    test_case_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    case = _authorized_case(db, user, test_case_id, write=True)
    db.delete(case)
    db.commit()
    return Response(status_code=204)


@router.post("/api/v1/specifications/{specification_id}/test-runs", response_model=TestRunOut, status_code=201)
def execute_all_tests(
    specification_id: UUID,
    payload: TestRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestRunOut:
    specification = _authorized_specification(db, user, specification_id, write=True)
    cases = db.query(TestCase).filter(TestCase.specification_id == specification_id, TestCase.is_enabled.is_(True)).all()
    if not payload.include_negative_tests:
        cases = [case for case in cases if case.category != "NEGATIVE_TEST"]
    run = _execute(db, specification, cases, payload)
    return TestRunOut.model_validate(run)


@router.post("/api/v1/test-runs/execute-selected", response_model=TestRunOut, status_code=201)
def execute_selected_tests(
    payload: SelectedTestRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestRunOut:
    cases = db.query(TestCase).filter(
        TestCase.id.in_(payload.test_case_ids),
        TestCase.is_enabled.is_(True),
    ).all()
    if len(cases) != len(set(payload.test_case_ids)):
        raise HTTPException(404, "One or more enabled test cases were not found.")
    specification_ids = {case.specification_id for case in cases}
    if len(specification_ids) != 1:
        raise HTTPException(400, "Selected test cases must belong to one specification.")
    if not payload.include_negative_tests:
        cases = [case for case in cases if case.category != "NEGATIVE_TEST"]
    specification = _authorized_specification(db, user, next(iter(specification_ids)), write=True)
    run = _execute(db, specification, cases, payload)
    return TestRunOut.model_validate(run)


@router.get("/api/v1/specifications/{specification_id}/test-runs", response_model=list[TestRunOut])
def list_test_runs(
    specification_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TestRunOut]:
    _authorized_specification(db, user, specification_id)
    runs = db.query(TestRun).filter(TestRun.specification_id == specification_id).order_by(TestRun.started_at.desc()).offset(offset).limit(limit).all()
    return [TestRunOut.model_validate(item) for item in runs]


@router.get("/api/v1/specifications/{specification_id}/testing-summary")
def testing_summary(
    specification_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    _authorized_specification(db, user, specification_id)
    case_count = db.query(func.count(TestCase.id)).filter(
        TestCase.specification_id == specification_id
    ).scalar() or 0
    run_count = db.query(func.count(TestRun.id)).filter(
        TestRun.specification_id == specification_id
    ).scalar() or 0
    result_counts = db.query(TestResult.status, func.count(TestResult.id)).join(
        TestRun, TestResult.test_run_id == TestRun.id
    ).filter(TestRun.specification_id == specification_id).group_by(TestResult.status).all()
    counts = {status: count for status, count in result_counts}
    average_response = db.query(func.avg(TestResult.response_time_ms)).join(
        TestRun, TestResult.test_run_id == TestRun.id
    ).filter(
        TestRun.specification_id == specification_id,
        TestResult.response_time_ms.is_not(None),
    ).scalar()
    latest_run = db.query(TestRun).filter(
        TestRun.specification_id == specification_id
    ).order_by(TestRun.started_at.desc()).first()
    recent_failures = db.query(TestResult).join(
        TestRun, TestResult.test_run_id == TestRun.id
    ).filter(
        TestRun.specification_id == specification_id,
        TestResult.status.in_(["FAILED", "ERROR"]),
    ).order_by(TestResult.executed_at.desc()).limit(10).all()
    executed = counts.get("PASSED", 0) + counts.get("FAILED", 0) + counts.get("ERROR", 0)
    return {
        "test_case_count": case_count,
        "test_run_count": run_count,
        "passed_tests": counts.get("PASSED", 0),
        "failed_tests": counts.get("FAILED", 0),
        "skipped_tests": counts.get("SKIPPED", 0),
        "error_tests": counts.get("ERROR", 0),
        "success_rate": round(counts.get("PASSED", 0) * 100 / executed, 1) if executed else None,
        "average_response_time_ms": float(average_response) if average_response is not None else None,
        "latest_run": TestRunOut.model_validate(latest_run).model_dump(mode="json") if latest_run else None,
        "recent_failures": [TestResultOut.model_validate(item).model_dump(mode="json") for item in recent_failures],
    }


@router.get("/api/v1/test-runs/{test_run_id}", response_model=TestRunOut)
def get_test_run(
    test_run_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestRunOut:
    run = _authorized_run(db, user, test_run_id)
    return TestRunOut.model_validate(run)


@router.get("/api/v1/test-runs/{test_run_id}/results", response_model=list[TestResultOut])
def get_test_results(
    test_run_id: UUID,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TestResultOut]:
    _authorized_run(db, user, test_run_id)
    results = db.query(TestResult).filter(TestResult.test_run_id == test_run_id).order_by(TestResult.executed_at).offset(offset).limit(limit).all()
    return [TestResultOut.model_validate(item) for item in results]


@router.get("/api/v1/test-results/{result_id}", response_model=TestResultOut)
def get_test_result(
    result_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestResultOut:
    result = db.get(TestResult, result_id)
    if not result:
        raise HTTPException(404, "Test result not found.")
    _authorized_run(db, user, result.test_run_id)
    return TestResultOut.model_validate(result)


@router.delete("/api/v1/test-runs/{test_run_id}", status_code=204)
def delete_test_run(
    test_run_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    run = _authorized_run(db, user, test_run_id, write=True)
    db.delete(run)
    db.commit()
    return Response(status_code=204)
