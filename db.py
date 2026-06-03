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
    Inserts a tour booking record directly into the database using a parameterized SQL query.
    Allows testing locally without needing the stored procedure created on the DB server yet.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Parameterized query defined inside the python file
        query = """
            INSERT INTO dbo.WN_BookTour (Name, Email, Message, CreatedAt, PhoneNumber)
            VALUES (%s, %s, %s, GETDATE(), %s)
        """
        
        # Execute with parameter binding (prevents SQL injection)
        cursor.execute(query, (name, email, message, phone_number))
        conn.commit()
        
        # Fetch the newly generated ID
        cursor.execute("SELECT @@IDENTITY")
        row = cursor.fetchone()
        new_id = row[0] if row else None
        
        return new_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
