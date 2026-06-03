import pymssql
import os

# Connection parameters with defaults pointing to the public environment
DB_SERVER = os.getenv("DB_SERVER")
DB_PORT = int(os.getenv("DB_PORT"))
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

def get_all_spaces():
    """
    Fetches all active spaces from WN_Spaces, joining their Location and SpaceType details.
    """
    conn = get_connection()
    try:
        # Use dictionary cursor for clean mapping to JSON
        cursor = conn.cursor(as_dict=True)
        
        query = """
            SELECT 
                s.Id AS id,
                s.Name AS name,
                l.Name AS locationName,
                st.Description AS spaceTypeName,
                st.Capacity AS capacity,
                s.PricePerDay AS pricePerDay,
                s.Amenities AS amenities,
                s.ImageUrl AS imageUrl,
                CASE 
                    WHEN s.Status = 1 THEN 'available'
                    ELSE 'inactive'
                END AS status
            FROM dbo.WN_Spaces s
            LEFT JOIN dbo.WN_Locations l ON s.LocationId = l.Id
            LEFT JOIN dbo.WN_SpaceTypes st ON s.SpaceTypeId = st.Id
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Ensure Decimals are converted to floats/ints for JSON serialization compatibility
        for row in rows:
            if row.get("pricePerDay") is not None:
                row["pricePerDay"] = float(row["pricePerDay"])
                
        return rows
    except Exception as e:
        raise e
    finally:
        conn.close()
