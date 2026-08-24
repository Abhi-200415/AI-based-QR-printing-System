from sqlalchemy import text
from app.database.connection import engine

def main():

    with engine.begin() as connection:

        connection.execute(
            text(
                """
                ALTER TABLE shop_owners
                ADD COLUMN IF NOT EXISTS qr_token VARCHAR(100) UNIQUE;

                ALTER TABLE shop_owners
                ADD COLUMN IF NOT EXISTS qr_path VARCHAR(255);
                """
            )
        )

    print("QR database migration completed successfully.")


if __name__ == "__main__":
    main()
