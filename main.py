from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
try:
    from api.db import book_tour, get_all_spaces
except ImportError:
    from db import book_tour, get_all_spaces

app = FastAPI(
    title="WorkNest API",
    description="FastAPI Backend for WorkNest Mobile application using SQL Server Stored Procedures",
    version="1.0.0"
)

# Enable CORS (Cross-Origin Resource Sharing) so frontend apps can communicate with it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic schema matching the React Native payload
class ContactRequest(BaseModel):
    fullName: str = Field(..., min_length=1, max_length=255, description="Full Name of the user")
    email: EmailStr = Field(..., description="Valid Email address")
    message: str = Field(..., min_length=1, max_length=100, description="Short message/notes (Max 100 characters)")
    phone: str = Field(..., min_length=1, max_length=20, description="Phone number (Max 20 characters)")

@app.get("/")
def read_root():
    return {
        "app": "WorkNest FastAPI Backend",
        "status": "healthy",
        "docs_url": "/docs"
    }

# Expose endpoints for both /api/contact, /contact and /api/book-tour to be compatible with all frontends
@app.post("/api/contact", status_code=status.HTTP_201_CREATED)
@app.post("/contact", status_code=status.HTTP_201_CREATED)
@app.post("/api/book-tour", status_code=status.HTTP_201_CREATED)
def create_book_tour(payload: ContactRequest):
    """
    Endpoint to receive tour booking requests and save them using a stored procedure.
    """
    try:
        new_id = book_tour(
            name=payload.fullName,
            email=payload.email,
            message=payload.message,
            phone_number=payload.phone
        )
        return {
            "isSuccessful": True,  # Mobile app checks response?.isSuccessful
            "message": "Tour booking successfully recorded.",
            "data": {
                "id": new_id,
                "fullName": payload.fullName,
                "email": payload.email,
                "phone": payload.phone
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database execution error: {str(e)}"
        )

@app.get("/api/space")
@app.get("/space")
def list_spaces():
    """
    Endpoint to retrieve all active coworking spaces from the database.
    """
    try:
        spaces = get_all_spaces()
        return spaces
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database execution error: {str(e)}"
        )
