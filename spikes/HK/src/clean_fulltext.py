"""
Clean existing full_text data in the database.

Applies text_preprocessor to remove garbled text, headers, and table fragments.

Run with: python src/clean_fulltext.py
"""

import psycopg2
from text_preprocessor import preprocess_full_text


def clean_existing_fulltext():
    """Re-process all full_text entries in the database."""
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user="oaria",
        password="oaria123",
        database="oaria"
    )
    cur = conn.cursor()

    # Get all papers with full_text
    cur.execute("""
        SELECT openalex_id, title, full_text
        FROM papers
        WHERE full_text IS NOT NULL AND full_text != ''
    """)
    papers = cur.fetchall()

    print(f"Found {len(papers)} papers with full text")

    cleaned = 0
    removed = 0

    for openalex_id, title, full_text in papers:
        # Apply preprocessing
        clean_text = preprocess_full_text(full_text)

        if len(clean_text) < 100:
            # Text was mostly garbage, remove it
            cur.execute(
                "UPDATE papers SET full_text = NULL WHERE openalex_id = %s",
                (openalex_id,)
            )
            removed += 1
            print(f"  REMOVED: {title[:50]}... (was {len(full_text)} chars, now garbage)")
        elif clean_text != full_text:
            # Text was cleaned - update it
            cur.execute(
                "UPDATE papers SET full_text = %s WHERE openalex_id = %s",
                (clean_text, openalex_id)
            )
            cleaned += 1
            reduction = 100 - (len(clean_text) / len(full_text) * 100)
            print(f"  CLEANED: {title[:50]}... ({len(full_text)} -> {len(clean_text)} chars, -{reduction:.1f}%)")

    conn.commit()
    cur.close()
    conn.close()

    print(f"\nDone!")
    print(f"  Cleaned: {cleaned}")
    print(f"  Removed (garbage): {removed}")
    print(f"  Unchanged: {len(papers) - cleaned - removed}")


if __name__ == "__main__":
    clean_existing_fulltext()
