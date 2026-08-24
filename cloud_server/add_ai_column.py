from sqlalchemy import text

from app.database.connection import engine


def main():

    with engine.begin() as connection:

        connection.execute(
            text(
                """
                ALTER TABLE active_jobs
                ADD COLUMN IF NOT EXISTS actual_seconds INTEGER;
                """
            )
        )

    print("AI column migration completed successfully.")


if __name__ == "__main__":
    main()