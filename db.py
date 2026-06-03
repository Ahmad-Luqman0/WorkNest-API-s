import pymssql
import os

# Connection parameters with defaults pointing to the public environment
DB_SERVER = os.getenv("DB_SERVER", "119.159.146.178")
DB_PORT = int(os.getenv("DB_PORT", "1450"))
DB_USER = os.getenv("DB_USER", "workernet")
DB_PASSWORD = os.getenv("DB_PASSWORD", "workernet123")
DB_NAME = os.getenv("DB_NAME", "SAC400")

def get_connection():
    """Establishes and returns a connection to the SQL Server database."""
    return pymssql.connect(
        server=DB_SERVER,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

def book_tour(name: str, email: str, message: str, phone_number: str):
    """
    Executes the stored procedure dbo.sp_BookTour_Insert to record a tour booking.
    Returns the ID of the newly created booking record.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Call the stored procedure using parameter binding (prevents inline query SQL injection)
        cursor.callproc("dbo.sp_BookTour_Insert", (name, email, message, phone_number))
        
        # In pymssql, callproc execution requires fetching results and committing transaction
        results = cursor.fetchall()
        conn.commit()
        
        new_id = None
        if results:
            new_id = results[0][0]
            
        return new_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
