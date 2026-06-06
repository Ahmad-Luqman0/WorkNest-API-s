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
        get_user_id_by_email,
        get_all_locations,
        get_booking_by_id,
        create_payment,
        get_all_users,
        get_all_bookings,
        get_all_payments,
        get_all_space_types,
        get_all_contacts,
        get_all_memberships,
        insert_space,
        update_space
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
        get_user_id_by_email,
        get_all_locations,
        get_booking_by_id,
        create_payment,
        get_all_users,
        get_all_bookings,
        get_all_payments,
        get_all_space_types,
        get_all_contacts,
        get_all_memberships,
        insert_space,
        update_space
        
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

class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    phone: Optional[str] = None

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: Optional[str] = None

class GoogleLoginRequest(BaseModel):
    idToken: str
    email: EmailStr
    firstName: Optional[str] = None
    lastName: Optional[str] = None

class CardPaymentRequest(BaseModel):
    bookingId: int
    cardHolderName: str
    cardNumber: str
    expiryMonth: str
    expiryYear: str
    cvv: str

class CounterPaymentRequest(BaseModel):
    bookingId: int
    amount: float

class VoucherGenerateRequest(BaseModel):
    bookingId: int
    amount: float

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
    totalAmount: Optional[float] = None

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
def create_book_tour(payload: ContactRequest, x_user_email: Optional[str] = Header(None)):
    try:
        user_id = None
        if x_user_email:
            user_id = get_user_id_by_email(x_user_email)
            
        new_id = book_tour(
            name=payload.fullName,
            email=payload.email,
            message=payload.message,
            phone_number=payload.phone,
            user_id=user_id
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

# --- Locations API ---
@app.get("/api/location")
@app.get("/location")
def list_locations():
    try:
        return get_all_locations()
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
        
        amount = payload.totalAmount or 0.0
        print(f"[booking] totalAmount received: {payload.totalAmount}, using: {amount}")
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
                "totalAmount": amount,
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

# --- Booking Details API ---
@app.get("/api/booking/{id}")
@app.get("/booking/{id}")
def get_booking(id: int, x_user_email: Optional[str] = Header(None)):
    try:
        user_id = DEFAULT_USER_ID
        if x_user_email:
            resolved_id = get_user_id_by_email(x_user_email)
            if resolved_id:
                user_id = resolved_id
        
        booking_data = get_booking_by_id(user_id, id)
        if not booking_data:
            raise HTTPException(status_code=404, detail="Booking not found")
        return {
            "isSuccessful": True,
            "message": "Booking retrieved successfully.",
            "data": booking_data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database execution error: {str(e)}"
        )

# --- Payment Gateways API ---
@app.post("/api/payment/card")
@app.post("/payment/card")
def process_card_payment(payload: CardPaymentRequest, x_user_email: Optional[str] = Header(None)):
    try:
        user_id = DEFAULT_USER_ID
        if x_user_email:
            resolved_id = get_user_id_by_email(x_user_email)
            if resolved_id:
                user_id = resolved_id
        
        # Fetch booking to get the amount
        booking_data = get_booking_by_id(user_id, payload.bookingId)
        if not booking_data:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        amount = booking_data["totalAmount"]
        import random
        tx_ref = f"TXN-CARD-{payload.bookingId}-{random.randint(100000, 999999)}"
        
        # Record payment in DB
        create_payment(
            user_id=user_id,
            booking_id=payload.bookingId,
            amount=amount,
            payment_method="Card",
            transaction_ref=tx_ref
        )
        
        return {
            "isSuccessful": True,
            "message": "Card payment processed successfully.",
            "transactionRef": tx_ref
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database execution error: {str(e)}"
        )

@app.post("/api/payment/voucher/generate")
@app.post("/payment/voucher/generate")
def generate_voucher(payload: VoucherGenerateRequest, x_user_email: Optional[str] = Header(None)):
    try:
        user_id = DEFAULT_USER_ID
        if x_user_email:
            resolved_id = get_user_id_by_email(x_user_email)
            if resolved_id:
                user_id = resolved_id
        
        # Verify booking exists
        booking_data = get_booking_by_id(user_id, payload.bookingId)
        if not booking_data:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        import random
        from datetime import datetime, timedelta
        voucher_number = f"1BILL{payload.bookingId:04d}{random.randint(10000, 99999):05d}"
        expiry_date = (datetime.utcnow() + timedelta(days=3)).isoformat() + "Z"
        
        # Record payment in DB with "Voucher" method
        create_payment(
            user_id=user_id,
            booking_id=payload.bookingId,
            amount=payload.amount,
            payment_method="Voucher",
            transaction_ref=voucher_number
        )
        
        return {
            "isSuccessful": True,
            "message": "Voucher generated successfully.",
            "voucherNumber": voucher_number,
            "expiryDate": expiry_date,
            "amount": payload.amount,
            "paymentChannels": [
                "Any bank branch (over the counter)",
                "ATM (Bill Payment)",
                "Internet Banking",
                "EasyPaisa / JazzCash",
                "HBL Mobile / MCB Mobile"
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database execution error: {str(e)}"
        )

# --- Auth Sync Wrappers ---
@app.post("/api/auth/register")
@app.post("/auth/register")
def register_user(payload: UserRegisterRequest):
    try:
        user_id = sync_user(
            email=payload.email,
            first_name=payload.firstName or "",
            last_name=payload.lastName or "",
            phone=payload.phone
        )
        return {
            "isSuccessful": True,
            "message": "User registered/synchronized successfully.",
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

@app.post("/api/auth/login")
@app.post("/auth/login")
def login_user(payload: UserLoginRequest):
    try:
        user_id = get_user_id_by_email(payload.email)
        return {
            "isSuccessful": True,
            "message": "User logged in/synchronized successfully.",
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

@app.post("/api/auth/google-login")
@app.post("/auth/google-login")
def google_login_user(payload: GoogleLoginRequest):
    try:
        user_id = sync_user(
            email=payload.email,
            first_name=payload.firstName or "",
            last_name=payload.lastName or ""
        )
        return {
            "isSuccessful": True,
            "message": "Google user synchronized successfully.",
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


# --- Admin: All Users ---
@app.get("/api/user")
@app.get("/user")
def list_users():
    try:
        return get_all_users()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Admin: All Bookings ---
@app.get("/api/booking")
@app.get("/booking")
def list_all_bookings():
    try:
        return get_all_bookings()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Admin: All Payments ---
@app.get("/api/payment")
@app.get("/payment")
def list_all_payments():
    try:
        return get_all_payments()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Admin: Space Types ---
@app.get("/api/spacetype")
@app.get("/spacetype")
def list_space_types():
    try:
        return get_all_space_types()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Admin: All Contacts (GET) ---
@app.get("/api/contact")
@app.get("/contact")
def list_contacts():
    try:
        return get_all_contacts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Admin: All Memberships ---
@app.get("/api/membership")
@app.get("/membership")
def list_memberships():
    try:
        return get_all_memberships()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# --- Admin: Create Space ---
class SpaceInsertRequest(BaseModel):
    name: str
    locationId: int
    spaceTypeId: int
    code: Optional[str] = None
    description: Optional[str] = None
    floor: Optional[str] = None
    pricePerDay: Optional[float] = None
    pricePerHour: Optional[float] = None
    imageUrl: Optional[str] = None
    amenities: Optional[str] = None

@app.post("/api/space", status_code=status.HTTP_201_CREATED)
@app.post("/space", status_code=status.HTTP_201_CREATED)
def create_space(payload: SpaceInsertRequest):
    try:
        new_id = insert_space(
            name=payload.name,
            location_id=payload.locationId,
            space_type_id=payload.spaceTypeId,
            code=payload.code,
            description=payload.description,
            floor=payload.floor,
            price_per_day=payload.pricePerDay,
            price_per_hour=payload.pricePerHour,
            image_url=payload.imageUrl,
            amenities=payload.amenities
        )
        return {"isSuccessful": True, "message": "Space created successfully.", "data": {"id": new_id}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database execution error: {str(e)}")
class SpaceUpdateRequest(BaseModel):
    name: Optional[str] = None
    locationId: Optional[int] = None
    spaceTypeId: Optional[int] = None
    code: Optional[str] = None
    description: Optional[str] = None
    floor: Optional[str] = None
    pricePerDay: Optional[float] = None
    pricePerHour: Optional[float] = None
    imageUrl: Optional[str] = None
    amenities: Optional[str] = None

@app.put("/api/space/{id}")
@app.put("/space/{id}")
def edit_space(id: int, payload: SpaceUpdateRequest):
    try:
        update_space(id, payload.name, payload.locationId, payload.spaceTypeId,
            payload.code, payload.description, payload.floor,
            payload.pricePerDay, payload.pricePerHour, payload.imageUrl, payload.amenities)
        return {"isSuccessful": True, "message": "Space updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database execution error: {str(e)}")
