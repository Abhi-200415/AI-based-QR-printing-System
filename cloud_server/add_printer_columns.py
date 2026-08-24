from sqlalchemy import text

from app.database.connection import engine


columns = {
    "is_physical": "BOOLEAN NOT NULL DEFAULT TRUE",
    "is_virtual": "BOOLEAN NOT NULL DEFAULT FALSE",
    "is_available": "BOOLEAN NOT NULL DEFAULT FALSE"
}


with engine.begin() as connection:

    for column_name, definition in columns.items():

        exists = connection.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'printers'
                    AND column_name = :column_name
                )
                """
            ),
            {
                "column_name": column_name
            }
        ).scalar()

        if not exists:

            connection.execute(
                text(
                    f"""
                    ALTER TABLE printers
                    ADD COLUMN {column_name}
                    {definition}
                    """
                )
            )

            print(
                f"Added: {column_name}"
            )

        else:

            print(
                f"Already exists: {column_name}"
            )


print(
    "Printer database migration completed."
)