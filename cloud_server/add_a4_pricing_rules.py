from sqlalchemy import text
from app.database.connection import engine


OWNER_ID = "71de5df6-af24-4ff8-a899-5511d9fc3ff4"


def main():

    with engine.begin() as connection:

        connection.execute(
            text(
                """
                INSERT INTO pricing_rules
                (
                    pricing_id,
                    owner_id,
                    paper_size,
                    print_type,
                    duplex,
                    page_from,
                    page_to,
                    price_per_page,
                    is_active
                )
                VALUES
                (
                    gen_random_uuid(),
                    :owner_id,
                    'A4',
                    'COLOR',
                    false,
                    1,
                    999999,
                    5.00,
                    true
                ),
                (
                    gen_random_uuid(),
                    :owner_id,
                    'A4',
                    'BW',
                    true,
                    1,
                    999999,
                    1.00,
                    true
                ),
                (
                    gen_random_uuid(),
                    :owner_id,
                    'A4',
                    'COLOR',
                    true,
                    1,
                    999999,
                    4.00,
                    true
                );
                """
            ),
            {
                "owner_id": OWNER_ID
            }
        )

    print("A4 pricing rules added successfully.")


if __name__ == "__main__":
    main()
