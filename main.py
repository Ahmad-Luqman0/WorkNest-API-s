from fastapi import FastAPI, HTTPException, status, Header
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
        get_my_payments,
        sync_user,
        get_user_id_by_email
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
        get_my_payments,
        sync_user,
        get_user_id_by_email
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

class UserSyncRequest(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    firstName: Optional[str] = Field(None, description="First name of the user")
    lastName: Optional[str] = Field(None, description="Last name of the user")
    phone: Optional[str] = Field(None, description="Contact/phone number")

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

# --- User Sync API ---
@app.post("/api/auth/sync")
@app.post("/auth/sync")
def sync_user_endpoint(payload: UserSyncRequest):
    try:
        user_id = sync_user(
            email=payload.email,
            first_name=payload.firstName or "",
            last_name=payload.lastName or "",
            phone=payload.phone
        )
        return {
            "isSuccessful": True,
            "message": "User synchronized successfully.",
            "data": {
                "id": user_id,
                "email": payload.email
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database execution error: {str(e)}"
        )

# --- Bookings API ---
@app.get("/api/booking/my")
@app.get("/booking/my")
def list_my_bookings(x_user_email: Optional[str] = Header(None)):
    try:
        user_id = DEFAULT_USER_ID
        if x_user_email:
            resolved_id = get_user_id_by_email(x_user_email)
            if resolved_id:
                user_id = resolved_id
        return get_my_bookings(user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database execution error: {str(e)}"
        )

@app.post("/api/booking", status_code=status.HTTP_201_CREATED)
@app.post("/booking", status_code=status.HTTP_201_CREATED)
def make_booking(payload: BookingRequest, x_user_email: Optional[str] = Header(None)):
    try:
        user_id = DEFAULT_USER_ID
        if x_user_email:
            resolved_id = get_user_id_by_email(x_user_email)
            if resolved_id:
                user_id = resolved_id
        
        amount = 0.0
        method = None
        ref = None
        
        if payload.payment:
            amount = payload.payment.amount
            method = payload.payment.method
            ref = payload.payment.referenceNumber or payload.payment.bankDepositId or ""
            
        booking_id = create_booking(
            user_id=user_id,
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
def cancel_my_booking(id: int, x_user_email: Optional[str] = Header(None)):
    try:
        user_id = DEFAULT_USER_ID
        if x_user_email:
            resolved_id = get_user_id_by_email(x_user_email)
            if resolved_id:
                user_id = resolved_id
        cancel_booking(user_id, id)
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
def list_my_payments(x_user_email: Optional[str] = Header(None)):
    try:
        user_id = DEFAULT_USER_ID
        if x_user_email:
            resolved_id = get_user_id_by_email(x_user_email)
            if resolved_id:
                user_id = resolved_id
        return get_my_payments(user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database execution error: {str(e)}"
        )

