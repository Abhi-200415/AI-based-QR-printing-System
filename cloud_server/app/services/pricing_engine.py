from sqlalchemy.orm import Session

from app.database.models import (
    JobFile,
    ActiveJob,
    PricingRule
)


def calculate_file_cost(
    file: JobFile,
    db: Session
):

    rule = (
        db.query(PricingRule)
        .filter(
            PricingRule.print_mode == file.print_mode,
            PricingRule.is_active == True
        )
        .first()
    )

    if not rule:
        return 0

    cost = (
        file.page_count
        * file.copies
        * float(rule.price_per_page)
    )

    file.estimated_print_cost = cost

    return cost


def calculate_job_cost(
    job_id,
    db: Session
):

    files = (
        db.query(JobFile)
        .filter(
            JobFile.job_id == job_id
        )
        .all()
    )

    total_cost = 0

    for file in files:

        total_cost += calculate_file_cost(
            file,
            db
        )

    job = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.job_id == job_id
        )
        .first()
    )

    if job:
        job.total_amount = total_cost

    db.commit()

    return total_cost