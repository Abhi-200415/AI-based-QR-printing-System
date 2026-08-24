from sqlalchemy import text

from app.database.connection import engine


def main():

    with engine.begin() as connection:

        # --------------------------------------------------
        # Create enum type if it does not already exist
        # --------------------------------------------------

        connection.execute(
            text(
                """
                DO $$
                BEGIN

                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_type
                        WHERE typname = 'pricingbasis'
                    ) THEN

                        CREATE TYPE pricingbasis AS ENUM (
                            'PER_SIDE',
                            'PER_SHEET'
                        );

                    END IF;

                END
                $$;
                """
            )
        )

        # --------------------------------------------------
        # Check whether column already exists
        # --------------------------------------------------

        exists = connection.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'shop_settings'
                    AND column_name = 'pricing_basis'
                )
                """
            )
        ).scalar()

        # --------------------------------------------------
        # Add column
        # --------------------------------------------------

        if not exists:

            connection.execute(
                text(
                    """
                    ALTER TABLE shop_settings
                    ADD COLUMN pricing_basis pricingbasis
                    NOT NULL
                    DEFAULT 'PER_SIDE';
                    """
                )
            )

            print(
                "Added: pricing_basis"
            )

        else:

            print(
                "Already exists: pricing_basis"
            )

    print(
        "Pricing basis database migration completed."
    )


if __name__ == "__main__":

    main()