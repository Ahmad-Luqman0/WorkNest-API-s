from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

try:
    from api.db import (
        book_tour, 
        get_all_spaces, 
        get_gallery_images, 
        get_pricing_plans, 
        get_my_bookings, 
        create_booking, 
        cancel_booking, 
        get_my_payments
    )
except ImportError:
    from db import (
        book_tour, 
        get_all_spaces, 
        get_gallery_images, 
        get_pricing_plans, 
        get_my_bookings, 
        create_booking, 
        cancel_booking, 
        get_my_payments
    )

app = FastAPI(
    title="WorkNest API",
    description="FastAPI Backend for WorkNest Mobile application using direct parameterized SQL queries.",
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

# Static User ID configuration for testing and database queries
DEFAULT_USER_ID = 1

# Pydantic schema matching the React Native Contact/Tour payload
class ContactRequest(BaseModel):
    fullName: str = Field(..., min_length=1, max_length=255, description="Full Name of the user")
    email: EmailStr = Field(..., description="Valid Email address")
    message: str = Field(..., min_length=1, max_length=100, description="Short message/notes")
    phone: str = Field(..., min_length=1, max_length=20, description="Phone number")

# Pydantic schemas for Bookings
class GuestDetails(BaseModel):
    name: str
    email: str
    phone: str

class PaymentDetails(BaseModel):
    method: str
    amount: float
    voucherCode: Optional[str] = None
    bankDepositId: Optional[str] = None
    referenceNumber: Optional[str] = None

class BookingRequest(BaseModel):
    spaceId: int
    startDateTime: str
    endDateTime: str
    notes: Optional[str] = None
    guest: Optional[GuestDetails] = None
    payment: Optional[PaymentDetails] = None

@app.get("/")
def read_root():
    return {
        "app": "WorkNest FastAPI Backend",
        "status": "healthy",
        "docs_url": "/docs"
    }

# --- Contact & Tour API ---
@app.post("/api/contact", status_code=status.HTTP_201_CREATED)
@app.post("/contact", status_code=status.HTTP_201_CREATED)
@app.post("/api/book-tour", status_code=status.HTTP_201_CREATED)
def create_book_tour(payload: ContactRequest):
    try:
        new_id = book_tour(
            name=payload.fullName,
            email=payload.email,
            message=payload.message,
            phone_number=payload.phone
        )
        return {
            "isSuccessful": True,
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

# --- Spaces API ---
@app.get("/api/space")
@app.get("/space")
def list_spaces():
    try:
        return get_all_spaces()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database execution error: {str(e)}"
        )

# --- Gallery API ---
@app.get("/api/gallery")
@app.get("/gallery")
def list_gallery():
    try:
        return get_gallery_images()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database execution error: {str(e)}"
        )

# --- Pricing Plans API ---
@app.get("/api/pricingplan")
@app.get("/pricingplan")
def list_pricing_plans():
    try:
        return get_pricing_plans()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database execution error: {str(e)}"
        )

# --- Bookings API ---
@app.get("/api/booking/my")
@app.get("/booking/my")
def list_my_bookings():
    try:
        return get_my_bookings(DEFAULT_USER_ID)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database execution error: {str(e)}"
        )

@app.post("/api/booking", status_code=status.HTTP_201_CREATED)
@app.post("/booking", status_code=status.HTTP_201_CREATED)
def make_booking(payload: BookingRequest):
    try:
        amount = 0.0
        method = None
        ref = None
        
        if payload.payment:
            amount = payload.payment.amount
            method = payload.payment.method
            ref = payload.payment.referenceNumber or payload.payment.bankDepositId or ""
            
        booking_id = create_booking(
            user_id=DEFAULT_USER_ID,
            space_id=payload.spaceId,
            start_date=payload.startDateTime,
            end_date=payload.endDateTime,
            notes=payload.notes or "",
            amount=amount,
            payment_method=method,
            reference_number=ref
        )
        return {
            "isSuccessful": True,
            "message": "Booking successful.",
            "data": {
                "id": booking_id,
                "spaceId": payload.spaceId,
                "amount": amount
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database execution error: {str(e)}"
        )

@app.patch("/api/booking/{id}/cancel")
@app.patch("/booking/{id}/cancel")
def cancel_my_booking(id: int):
    try:
        cancel_booking(DEFAULT_USER_ID, id)
        return {
            "isSuccessful": True,
            "message": "Booking successfully cancelled."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database execution error: {str(e)}"
        )

# --- Payments API ---
@app.get("/api/payment/my")
@app.get("/payment/my")
def list_my_payments():
    try:
        return get_my_payments(DEFAULT_USER_ID)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database execution error: {str(e)}"
        )
