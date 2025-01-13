from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth import login, authenticate
from django.contrib import messages
from core.models import UserModule, Customer, SpecialRequest, Cruise, Feedback, Booking, OnboardService, Passenger, CustomerBooking, LoyaltyProgram, Payment, Invoice, Notification, RefundRequest
from django.http import HttpResponse, HttpResponseRedirect
from django.template.loader import get_template
from customer.forms import CustomerSignupForm, LoginForm, CustomerProfileForm, CustomPasswordChangeForm, UserProfileForm, SpecialRequestForm, FeedbackForm, PassengerFormSet
from django.views.decorators.http import require_POST
from django.contrib.auth import logout, update_session_auth_hash, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.shortcuts import render, redirect
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import get_user_model 
import json
from django.forms import modelformset_factory
from django.views.decorators.csrf import csrf_exempt, csrf_protect
import logging
import random, string
from decimal import Decimal
from django.core.exceptions import ObjectDoesNotExist
import uuid
import io
import qrcode
from io import BytesIO
from django.template.loader import render_to_string
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import tempfile
from PIL import Image
import os
import base64

def customer_homepage(request):
    return render(request, 'customer/homepage.html')

def customer_about(request):
    return render(request, 'customer/custabout.html')

def services(request):
    return render(request, 'customer/service.html')

def destinations(request):
    return render(request, 'customer/destination.html')

def explore_cruises(request):
    cruises = Cruise.objects.all()  # Get all cruises
    context = {
        'cruises': cruises,
    }
    return render(request, 'customer/explore_cruises.html', context )

def book_now(request):
    # If user is logged in, redirect to the booking page or any other page
    if request.user.is_authenticated:
        return HttpResponseRedirect('/book-now/')  # Redirect to the actual booking page

    return render(request, 'customer/book_now.html')


def get_login_status(request):
    if request.user.is_authenticated:
        role = request.user.role if hasattr(request.user, 'role') else 'customer'  # Assuming default is 'customer'
        return JsonResponse({
            'is_logged_in': True,
            'role': role
        })
    else:
        return JsonResponse({
            'is_logged_in': False,
            'role': None
        })

@require_POST
def customer_signup(request):
    form = CustomerSignupForm(request.POST)
    if form.is_valid():
        customer = form.save(commit=False)
        user = customer.user  # Assuming customer.user is correctly set up to reference UserModule
        user.save()  # Save the User instance
        customer.save()  # Save the Customer instance

        # Return JSON on success
        return JsonResponse({'status': 'success', 'message': 'Signup successful!'})
    else:
        # Ensure JSON error response for frontend to read easily
        return JsonResponse({
            'status': 'error',
            'message': 'Signup failed. Please check the errors.',
            'errors': form.errors  # Include form errors here
        }, status=400)

                        
@require_POST
def login_view(request):
    try:
        data = json.loads(request.body)  # Parse JSON data from request body
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)

    form = LoginForm(data)

    if form.is_valid():
        email = form.cleaned_data['username']  # Assuming 'username' is the email field
        password = form.cleaned_data['password']

        user = authenticate(request, username=email, password=password)

        if user is not None and user.is_active:
            login(request, user)
            return JsonResponse({'status': 'success', 'message': "Login successful!"})
        else:
            return JsonResponse({'status': 'error', 'message': "Login failed. Check your email and password."})
    
    # Form is not valid
    errors = {field: error[0] for field, error in form.errors.items()}  # Extract specific error messages
    return JsonResponse({'status': 'error', 'message': "Validation error", 'errors': errors})



@require_POST
def logout_view(request):
    logout(request)  # Log out the user
    return JsonResponse({'status': 'success', 'message': "Logged out successfully."})

MEMBERSHIP_TIERS = [
    {
        'id': 1,
        'name': 'Bronze',
        'price': 19.99,
        'description': 'Start your journey with basic perks and discounts.',
    },
    {
        'id': 2,
        'name': 'Silver',
        'price': 49.99,
        'description': 'Enjoy Bronze benefits plus faster support and bonuses.',
    },
    {
        'id': 3,
        'name': 'Gold',
        'price': 99.99,
        'description': 'Access VIP events, premium upgrades, and Silver perks.',
    },
    {
        'id': 4,
        'name': 'Diamond',
        'price': 199.99,
        'description': 'Experience ultimate luxury, exclusive perks, and top-tier access.',
    },
]



def generate_card_number():
    """Generates a random 12-digit card number."""
    return ''.join(random.choices(string.digits, k=12))

def generate_passcode(username):
    """Generates a passcode based on the username with numbers and symbols."""
    return f"{username}{random.randint(1000, 9999)}@!%"

def purchase_membership(request):
    if request.method == 'POST':
        membership_id = request.POST.get('membership')
        membership = next(m for m in MEMBERSHIP_TIERS if m['id'] == int(membership_id))

        # Generate card number and passcode
        card_number = generate_card_number()
        passcode = generate_passcode(request.user.username)

        # Retrieve the customer instance
        customer = Customer.objects.get(user=request.user)  # Get the customer related to the logged-in user
        
        if not customer.loyalty_program:
            # Create a new LoyaltyProgram instance
            loyalty_program = LoyaltyProgram.objects.create(
                customer=customer,
                points=0,  # Initialize points
                level=membership['name'],  # Assign the selected membership level
                loyalty_card_number=card_number,
                password=passcode
            )

            # Link the loyalty program to the customer and set them as a loyalty member
            customer.loyalty_program = loyalty_program
            customer.loyalty_member = True
            customer.save()
        else:
            # If the customer already has a loyalty program, update the level and card
            loyalty_program = customer.loyalty_program
            loyalty_program.level = membership['name']
            loyalty_program.loyalty_card_number = card_number
            loyalty_program.password = passcode
            loyalty_program.save()

        # Return success message with card details in JSON format for modal
        return JsonResponse({
            'status': 'success',
            'message': 'Membership purchased successfully!',
            'card_number': card_number,
            'passcode': passcode,
            'tier': membership['name'],
        })

    return render(request, 'customer/purchase_loyalty_membership.html', {'memberships': MEMBERSHIP_TIERS})

@login_required
def loyalty_program_details(request):
    try:
        # Retrieve the customer from the Customer model using the logged-in user's ID
        customer = Customer.objects.get(user=request.user)
    except Customer.DoesNotExist:
        messages.error(request, "Customer profile not found.")
        return redirect('profile')  # Redirect to the profile page if customer is not found

    # Fetch the customer's associated loyalty program
    try:
        loyalty_program = LoyaltyProgram.objects.get(customer=customer)
    except LoyaltyProgram.DoesNotExist:
        loyalty_program = None

    if not loyalty_program:
        # If no loyalty program is found, redirect to the purchase page
        messages.info(request, "You are not a member of the Loyalty Program. Purchase a card to join!")
        return redirect('purchase_loyalty')

    # Render the loyalty program details page
    return render(request, 'customer/loyalty_program.html', {
        'loyalty_program': loyalty_program
    })

@login_required
def resume_booking(request, booking_id):
    customer = get_object_or_404(Customer, user=request.user)

    # Fetch the booking or return a 404 if not found
    booking = get_object_or_404(Booking, id=booking_id, customer=customer)

    if booking.status == 'Paused':
        # If the booking status is 'Paused', resume it by setting the status to 'Pending'
        booking.status = 'Pending'
        booking.save()
        messages.success(request, "Booking resumed! You can now continue your booking process.")
    elif booking.status == 'Pending':
        # If the booking status is already 'Pending', just inform the user
        messages.info(request, "You're already in the process of booking.")
    else:
        # If the booking is in any other state, notify the user
        messages.warning(request, "This booking cannot be resumed at the moment.")
    
    DEFAULT_PAYMENT_METHOD = 'Credit Card'
    DEFAULT_ROOM_TYPE = 'Economy'

    # Determine the next step in the booking process and redirect accordingly
    if booking.cruise is None:
        messages.info(request, "Please select a cruise to continue.")
        return redirect('select_cruise', booking_id=booking.id)
    elif not booking.passengers.exists():
        messages.info(request, "Please add passengers to your booking.")
        return redirect('add_passenger', booking_id=booking.id)
    elif not booking.onboard_services.exists():
        messages.info(request, "Select additional services for your booking.")
        return redirect('select-services', booking_id=booking.id)
    elif booking.payment_method == DEFAULT_PAYMENT_METHOD and booking.room_type == DEFAULT_ROOM_TYPE:
        messages.info(request, "Please provide additional booking details.")
        return redirect('save-other-details', booking_id=booking.id)
    elif booking.total_price is None or booking.total_price <= 0:
        messages.info(request, "Please review your booking summary.")
        return redirect('booking_summary', booking_id=booking.id)
    elif booking.payment_status == 'Unpaid':
        messages.info(request, "Your booking is pending payment.")
        return redirect('payment_page', booking_id=booking.id)
    else:
        messages.success(request, "Your booking is confirmed.")
        return redirect('payment_success', booking_id=booking.id)


@login_required
def start_booking(request):
    customer = get_object_or_404(Customer, user=request.user)

    # Check if the user has a paused booking
    paused_booking = Booking.objects.filter(customer=customer, status='Paused').first()

    if request.method == 'POST':
        action = request.POST.get('action')  # Get the action from the form (resume or delete)
        
        if action == 'resume' and paused_booking:
            # Resume the booking (change status from 'Paused' to 'Pending')
            paused_booking.status = 'Pending'
            paused_booking.save()
            messages.success(request, "Booking resumed! You can now continue your booking process.")
            return redirect('resume-booking', booking_id=paused_booking.id)  # Redirect to resume booking
        elif action == 'delete' and paused_booking:
            # Delete the paused booking and redirect to the cruise selection page
            paused_booking.delete()
            messages.success(request, "Your paused booking has been deleted. You can now start a new booking.")
            return redirect('select-cruise')  # Redirect to select cruise page
        else:
            messages.warning(request, "No paused booking found.")
            return redirect('select-cruise')

    return render(request, 'customer/booking/start_booking.html', {'paused_booking': paused_booking})

@login_required
def select_cruise(request, booking_id=None):
    customer = get_object_or_404(Customer, user=request.user)

    if request.method == 'GET':
        # Retrieve all cruises for display
        cruises = Cruise.objects.all()

        context = {
            'cruises': cruises,
            'booking_id': booking_id,
        }
        return render(request, 'customer/booking/select_cruise.html', context)

    elif request.method == 'POST':
        # Handle cruise selection
        try:
            data = json.loads(request.body)
            cruise_id = data.get('cruise_id')

            if not cruise_id:
                return JsonResponse({'error': 'No cruise ID provided'}, status=400)

            cruise = get_object_or_404(Cruise, id=cruise_id)

            # If booking_id exists, resume the booking (if it was paused)
            if booking_id:
                booking = get_object_or_404(Booking, id=booking_id, customer=customer)
                if booking.status == 'Paused':
                    booking.status = 'Pending'  # Resume the paused booking
                booking.cruise = cruise
                booking.save()
            else:
                # If no booking_id, create a new booking (standard flow)
                # Create a new booking and assign the cruise
                booking = Booking.objects.create(
                    customer=customer,
                    cruise=cruise,  # Ensure cruise is assigned to the booking
                    status='Pending',  # Booking status is 'Pending' initially
                )

            return JsonResponse({
                'cruise_name': cruise.name,
                'status': 'Cruise Selected',
                'booking_id': booking.id,  # Return the booking ID
                'message': 'Your cruise selection has been saved successfully.',
            })

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    
@csrf_exempt
def update_booking_status(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        booking_id = data.get('booking_id')
        status = data.get('status')

        if booking_id and status:
            try:
                booking = Booking.objects.get(id=booking_id)
                booking.status = status
                booking.save()
                return JsonResponse({'status': 'success'})
            except Booking.DoesNotExist:
                return JsonResponse({'error': 'Booking not found'}, status=404)
        return JsonResponse({'error': 'Invalid data'}, status=400)

@csrf_exempt
def add_passenger(request, booking_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User is not authenticated'}, status=401)

    # Retrieve the customer object linked to the authenticated user
    customer = get_object_or_404(Customer, user=request.user)
    
    # Retrieve the booking object using the booking_id passed in the URL
    booking = get_object_or_404(Booking, id=booking_id)

    # Retrieve all bookings for the customer
    bookings = Booking.objects.filter(customer=customer)

    if booking.status == 'Paused':
        # If the booking is paused, inform the user and prompt them to resume it
        messages.info(request, "Your booking is paused. Please resume your booking.")
        return redirect('resume_booking', booking_id=booking.id)

    if request.method == 'POST':
        formset = PassengerFormSet(request.POST)

        if formset.is_valid():
            passengers = formset.save(commit=False)
            for passenger in passengers:
                passenger.booking = booking
                passenger.save()

            # Update the number of passengers in the booking
            booking.number_of_passengers = booking.passengers.count()
            booking.save()

            return JsonResponse({
                'status': 'success',
                'message': 'Passengers added successfully!',
            })
        else:
            # Collect and return all validation errors from the formset
            errors = formset.errors
            return JsonResponse({
                'status': 'error',
                'message': 'Form validation failed. Please check the details entered.',
                'errors': errors,
            }, status=400)

    # Pre-fill the first passenger form with the authenticated user's details
    customer_data = {
        'first_name': customer.first_name,
        'last_name': customer.last_name,
        'age': customer.age if hasattr(customer, 'age') else '',
        'gender': customer.gender if hasattr(customer, 'gender') else '',
        'passport_number': '',
        'nationality': customer.nationality if hasattr(customer, 'nationality') else '',
    }

    formset = PassengerFormSet(
        queryset=Passenger.objects.none(),
        initial=[customer_data]  # Pre-fill the first form
    )

    return render(request, 'customer/booking/add_passenger.html', {
        'formset': formset,
        'bookings': bookings,
        'booking_id': booking_id,
    })


@csrf_exempt
@login_required
def select_services(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, customer__user=request.user)
    onboard_services = OnboardService.objects.all()

    if booking.status == 'Paused':
        # If booking is paused, prompt the user to resume
        messages.info(request, "Your booking is paused. Please resume your booking.")
        return redirect('resume_booking', booking_id=booking.id)

    if request.method == 'POST':
        try:
            # Parse JSON data
            import json
            data = json.loads(request.body)
            selected_service_ids = data.get('services', [])
            
            # Retrieve selected services
            selected_services = OnboardService.objects.filter(id__in=selected_service_ids)
            
            # Update the booking with the selected services
            booking.onboard_services.set(selected_services)
            booking.save()

            return JsonResponse({
                'status': 'success',
                'message': 'Services selected successfully!',
                'selected_services': selected_service_ids,
                'booking_id': booking.id
            }, status=200)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    # For GET requests, render the template with services
    return render(request, 'customer/booking/select_services.html', {
        'onboard_services': onboard_services,
        'booking_id': booking_id
    })

@login_required
def save_other_details(request, booking_id):
    # Fetch the booking by its ID and ensure the user is the customer
    booking = get_object_or_404(Booking, id=booking_id, customer__user=request.user)

    if booking.status == 'Paused':
        # If booking is paused, prompt the user to resume
        messages.info(request, "Your booking is paused. Please resume your booking.")
        return redirect('resume_booking', booking_id=booking.id)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)  # Parse JSON body
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)

        # Extract fields from the request
        payment_method = data.get('payment_method', 'Credit Card')  # Default to 'Credit Card'
        travel_insurance = data.get('travel_insurance', 'off') == 'on'  # Convert "on" to True
        room_type = data.get('room_type', booking.room_type)

        # Loyalty program details
        loyalty_program_member = data.get('loyalty_program_member', 'off') == 'on'
        loyalty_card_number = data.get('loyalty_card_number', '').strip()
        loyalty_pass = data.get('loyalty_pass', '').strip()
        loyalty_level = data.get('loyalty_level', '').strip()  # Assume it is a dropdown field

        # Validate loyalty program details if loyalty program is selected
        if loyalty_program_member:
            loyalty_program = getattr(booking.customer, 'loyalty_program', None)
            if not loyalty_program:
                return JsonResponse({
                    'status': 'error',
                    'message': 'You are not enrolled in any loyalty program.'
                }, status=400)

            if not (
                loyalty_program.loyalty_card_number == loyalty_card_number and
                loyalty_program.password == loyalty_pass and
                loyalty_program.level == loyalty_level
            ):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Loyalty program details do not match our records.'
                }, status=400)

        # Update booking details
        booking.payment_method = payment_method
        booking.travel_insurance = travel_insurance
        booking.room_type = room_type
        booking.loyalty_program_member = loyalty_program_member
        booking.loyalty_card_number = loyalty_card_number if loyalty_program_member else None
        booking.loyalty_pass = loyalty_pass if loyalty_program_member else None
        booking.loyalty_level = loyalty_level if loyalty_program_member else None
        booking.save()

        return JsonResponse({
            'status': 'success',
            'message': 'Other details updated successfully!',
            'booking_id': booking.id
        }, status=200)

    # For GET requests, render the 'other_details.html' template
    return render(request, 'customer/booking/other_details.html', {
        'booking': booking,
        'booking_id': booking_id,
    })

def booking_summary(request, booking_id):
    # Get the booking object by its ID
    booking = get_object_or_404(Booking, id=booking_id)

    if booking.status == 'Paused':
        # If booking is paused, prompt the user to resume
        messages.info(request, "Your booking is paused. Please resume your booking.")
        return redirect('resume_booking', booking_id=booking.id)
    
    DEFAULT_PAYMENT_METHOD = 'Credit Card'
    DEFAULT_ROOM_TYPE = 'Economy'

    # Ensure all necessary booking details are complete
    if booking.cruise is None:
        return redirect('select_cruise', booking_id=booking.id)
    if not booking.passengers.exists():
        return redirect('add_passenger', booking_id=booking.id)
    if booking.onboard_services.count() == 0:
        return redirect('select-services', booking_id=booking.id)
    if booking.payment_method == DEFAULT_PAYMENT_METHOD and booking.room_type == DEFAULT_ROOM_TYPE:
        messages.info(request, "Please provide additional booking details.")
        return redirect('save-other-details', booking_id=booking.id)

    # Calculate the total price and breakdown
    total_price = booking.calculate_total_price()

    # Additional pricing breakdowns
    base_price = Decimal(booking.cruise.price_per_person) * Decimal(booking.passengers.count())
    room_price_value = booking.cruise.price_per_room_type.get(booking.room_type, 100)  # Default to 100
    room_price = Decimal(room_price_value)
    services_total_price = sum(Decimal(service.price) for service in booking.onboard_services.all())
    travel_insurance_price = (base_price + room_price + services_total_price) * Decimal(0.05)  # 5% insurance
    tax = (base_price + room_price + services_total_price + travel_insurance_price) * Decimal(0.10)  # 10% tax
    loyalty_discount = (
        Decimal(booking.customer.loyalty_program.points) * Decimal(0.05) 
        if booking.loyalty_program_member else Decimal(0)
    )
    discount = Decimal(0)
    for passenger in booking.passengers.all():
        if passenger.age <= 12:  # Child discount
            discount += base_price * Decimal(0.15)
        elif passenger.age >= 60:  # Elderly discount
            discount += base_price * Decimal(0.10)

    # Handle form submission (POST) to confirm booking
    if request.method == 'POST':
        booking.status = 'Confirmed'
        booking.payment_status = 'Pending'
        booking.save()
        return redirect('payment_page', booking_id=booking.id)

    # Context for the template
    context = {
        'booking': booking,
        'total_price': total_price.quantize(Decimal('0.001')),
        'base_price': base_price.quantize(Decimal('0.001')),
        'room_price': room_price.quantize(Decimal('0.001')),
        'services_total_price': services_total_price.quantize(Decimal('0.001')),
        'travel_insurance_price': travel_insurance_price.quantize(Decimal('0.001')),
        'tax': tax.quantize(Decimal('0.001')),
        'loyalty_discount': loyalty_discount.quantize(Decimal('0.001')),
        'discount': discount.quantize(Decimal('0.001')),
    }
    return render(request, 'customer/booking/booking_summary.html', context)

# View for the payment page
@login_required
def payment_page(request, booking_id):
    # Get the booking object by ID
    booking = get_object_or_404(Booking, id=booking_id, customer__user=request.user)

    # Initialize some variables
    total_price = booking.calculate_total_price()  # Assuming this method calculates total price for the booking

    if booking.status == 'Paused':
        # If booking is paused, prompt the user to resume
        messages.info(request, "Your booking is paused. Please resume your booking.")
        return redirect('resume_booking', booking_id=booking.id)

    # If the payment has already been made, redirect to success page
    if booking.payment_status == 'Paid':
        return redirect('payment_success', booking_id=booking.id)

    # Handle POST request to process payment
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        if payment_method not in ['Credit Card', 'PayPal', 'Bank Transfer']:
            return redirect('payment_success', booking_id=booking.id)  # Handle payment method failure gracefully

        # Create the Payment record
        payment = Payment.objects.create(
            booking=booking,
            amount=total_price,
            payment_method=payment_method,
            transaction_id=str(uuid.uuid4()),  # Generate a unique transaction ID
        )

        # Update the booking status to "Confirmed" and payment status to "Paid"
        booking.payment_status = 'Paid'
        booking.status = 'Confirmed'
        booking.save()

        # Redirect to the success page after successful payment
        return redirect('payment_success', booking_id=booking.id)

    # If it's a GET request, render the payment page with the total price
    return render(request, 'customer/booking/payment.html', {'booking': booking, 'total_price': total_price})


# View for successful payment
@login_required
def payment_success(request, booking_id):
    # Get the booking object by ID
    booking = get_object_or_404(Booking, id=booking_id, customer__user=request.user)

    # Check if the booking has a payment associated with it
    if not booking.payment_booking:
        messages.error(request, "Payment not completed. Please try again.")
        return redirect('payment_page', booking_id=booking.id)

    # Check if cabin and deck are already assigned, if not, assign them
    if not booking.cabin_number or not booking.deck_number:
        booking.assign_cabin_and_deck()  # Automatically assigns cabin and deck
        booking.save()  # Save the changes to the database
        messages.success(request, f"Cabin {booking.cabin_number} and Deck {booking.deck_number} have been successfully assigned.")
    else:
        messages.info(request, f"Booking already has Cabin {booking.cabin_number} and Deck {booking.deck_number} assigned.")

    # Send notification to customer
    Notification.objects.create(
        recipient=booking.customer.user,
        title="Booking Confirmed",
        message=f"Your booking with ID {booking.id} has been confirmed.",
    )

    # Send notification to all admins
    admin_users = UserModule.objects.filter(is_staff=True)
    for admin in admin_users:
        Notification.objects.create(
            recipient=admin,
            title="New Booking Added",
            message=f"A new booking with ID {booking.id} has been added.",
        )

    # Render the success page with booking details
    return render(request, 'customer/booking/paymentsuccess.html', {'booking': booking})

@login_required
def notifications(request):
    user = request.user
    # Fetch all notifications for the user (read and unread)
    all_notifications = Notification.objects.filter(recipient=user).order_by('-created_at')

    # Fetch only unread notifications for the dropdown
    unread_notifications = all_notifications.filter(is_read=False)
    unread_count = unread_notifications.count()

    # Fetch the latest 5 notifications for the "View All" page
    latest_notifications = all_notifications[:5]

    return render(request, 'customer/notifications.html', {
        'notifications': all_notifications,  # Show all notifications on "View All" page
        'unread_notifications': unread_notifications,  # For dropdown
        'latest_notifications': latest_notifications,  # Optional, for "View All" preview
        'unread_count': unread_count,
    })


@csrf_exempt
@login_required
def mark_all_notifications_read(request):
    if request.method == 'POST':
        try:
            # Mark all unread notifications as read
            notifications = Notification.objects.filter(recipient=request.user, is_read=False)
            notifications.update(is_read=True)

            # Recalculate unread count
            unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
            return JsonResponse({'success': True, 'unread_count': unread_count})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)



@login_required
def ticket_info(request):
    # Get the latest confirmed booking for the logged-in user
    try:
        booking = Booking.objects.filter(customer__user=request.user, status='Confirmed').latest('booking_date')
    except Booking.DoesNotExist:
        messages.error(request, "No confirmed bookings found.")
        return redirect('profile')

    # Generate a QR code for the ticket
    qr_data = f"Booking ID: {booking.id}\nCustomer: {booking.customer.user.username}\nCabin: {booking.cabin_number}\nDeck: {booking.deck_number}"
    qr = qrcode.make(qr_data)
    
    # Save the QR code image to a BytesIO object
    buffer = BytesIO()
    qr.save(buffer)
    buffer.seek(0)
    
    # Encode the image as base64
    qr_image = base64.b64encode(buffer.getvalue()).decode('utf-8')

    # Render the ticket page with the QR code
    context = {
        'booking': booking,
        'qr_image': qr_image,
    }
    return render(request, 'customer/ticket.html', context)


@login_required
def download_ticket_pdf(request):
    # Retrieve the latest booking for the logged-in user
    booking = Booking.objects.filter(customer__user=request.user).latest('booking_date')  # Adjust 'booking_date' if needed

    if not booking:
        # Handle case if no booking is found
        return redirect('profile')  # Redirect to profile or another page

    # Create the HTTP response with PDF content
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ticket_{booking.id}.pdf"'

    # Create a canvas for the PDF file
    c = canvas.Canvas(response, pagesize=letter)

    # Set up font
    c.setFont("Helvetica", 10)

    # Title
    c.setFont("Helvetica-Bold", 14)
    c.drawString(200, 750, f"Ticket for {booking.cruise.name}")

    # Add details to the PDF
    c.setFont("Helvetica", 10)
    c.drawString(50, 720, f"Cruise Name: {booking.cruise.name}")
    c.drawString(50, 700, f"Destination: {booking.cruise.destination.name}")
    c.drawString(50, 680, f"Departure Date: {booking.cruise.start_date}")
    c.drawString(50, 660, f"Cabin Number: {booking.cabin_number}")
    c.drawString(50, 640, f"Deck Number: {booking.deck_number}")
    
    # Add passengers' details
    passengers_text = "Passenger(s): "
    for passenger in booking.passengers.all():
        passengers_text += f"{passenger.first_name} {passenger.last_name}, "
    passengers_text = passengers_text.strip(', ')
    c.drawString(50, 620, passengers_text)

    # Add QR code (use the qrcode module to generate the QR)
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(f"Booking ID: {booking.id}")
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")

    # Create in-memory file for the QR code
    img_buffer = BytesIO()
    img.save(img_buffer)
    img_buffer.seek(0)

    # Convert the in-memory image buffer to a PIL Image
    pil_img = Image.open(img_buffer)

    # Use tempfile to create a temporary file that works on Windows
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')

    # Save image and ensure it's closed
    try:
        pil_img.save(temp_file, format='PNG')
        img_path = temp_file.name
        pil_img.close()
    finally:
        # Ensure the file is closed properly in all cases
        temp_file.close()

    # Add QR code image to PDF
    c.drawImage(img_path, 450, 570, width=100, height=100)

    # Finalize the PDF
    c.showPage()
    c.save()

    # Delete the temporary image file after generating the PDF
    os.remove(img_path)

    return response

def generate_invoice(request, booking_id):
    # Get the booking object
    booking = get_object_or_404(Booking, id=booking_id, customer__user=request.user)

    # Create or get the invoice
    invoice, created = Invoice.objects.get_or_create(
        booking=booking,
        defaults={
            'amount': booking.total_price,
            'transaction_id': booking.payment_booking.transaction_id,
            'status': 'Issued',
        }
    )

    # Mark the invoice as paid if it was just created
    if created:
        invoice.paid = True
        invoice.save()

    # If the invoice already exists, return it
    if not created:
        return redirect('invoice_download', invoice_id=invoice.id)

    # Create the PDF
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.drawString(100, 750, f"Invoice for Booking ID: {booking.id}")
    p.drawString(100, 730, f"Cruise Name: {booking.cruise.name}")
    p.drawString(100, 710, f"Room Type: {booking.room_type}")
    p.drawString(100, 690, f"Total Price: ${booking.total_price:.2f}")
    p.drawString(100, 670, f"Transaction ID: {invoice.transaction_id}")
    p.drawString(100, 650, f"Issued Date: {invoice.issued_date}")
    p.drawString(100, 630, f"Status: {invoice.status}")
    p.drawString(100, 610, f"Paid: {'Yes' if invoice.paid else 'No'}")
    p.showPage()
    p.save()

    # Return the PDF as a downloadable file
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{booking.id}.pdf"'
    return response

def cancel_booking(request, booking_id):
    """
    Handles booking cancellation. Removes booking, updates customer booking status, and increments cruise available seats.
    """
    booking = get_object_or_404(Booking, id=booking_id, customer__user=request.user)

    if request.method == 'POST':
        cancellation_reason = request.POST.get('cancellation_reason', 'No reason provided')

        # Update the CustomerBooking status
        try:
            customer_booking = CustomerBooking.objects.get(booking=booking)
            customer_booking.cancel_booking(reason=cancellation_reason)
        except CustomerBooking.DoesNotExist:
            messages.error(request, "Customer booking record not found.")
            return redirect('profile')  

        # Increment available seats in the Cruise model
        cruise = booking.cruise
        cruise.update_seat_availability(increment=True)

        # Remove the Booking object
        booking.delete()
        messages.success(request, "Booking canceled successfully. Seat availability updated.")

        return redirect('profile')  # Redirect to the user's dashboard after cancellation

    return render(request, 'customer/cancel_booking.html', {
        'booking': booking,
        'booking_id': booking.id,
        })

@csrf_exempt
@login_required
def refund_request(request, booking_id):
    user = request.user
    customer = get_object_or_404(Customer, user=user)
    booking = get_object_or_404(Booking, id=booking_id, customer=customer)

    if request.method == "POST" and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        print("Received POST request")
        try:
            final_price = request.POST.get('final_price', '').replace('$', '').strip()
            notes = request.POST.get('notes', '')
            
            if not final_price or not notes:
                return JsonResponse({'status': 'error', 'message': 'All fields are required.'})

            try:
                final_price = float(final_price)
            except ValueError:
                return JsonResponse({'status': 'error', 'message': 'Invalid price format.'})

            # Create the refund request
            print(f"Creating refund for booking {booking.id}")  # Debugging log
            refund = RefundRequest.objects.create(
                booking=booking,
                final_price=final_price,
                notes=notes,
                name=user.username,
                is_approved=False
            )
            print(f"Refund created: {refund}")  # Debugging log
            
            # Send notifications to all admins
            admin_users = UserModule.objects.filter(is_staff=True)
            for admin in admin_users:
                Notification.objects.create(
                    recipient=admin,
                    title="New Refund Request Submitted",
                    message=f"A new refund request for Booking ID {booking.id} has been submitted by {user.username}.",
                )

            cancel_booking_url = reverse('cancel_booking', kwargs={'booking_id': booking.id})
            return JsonResponse({'status': 'success', 'redirect_url': cancel_booking_url})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    context = {
        'name': user.username,
        'email': user.email,
        'booking_id': booking.id,
        'total_price': booking.total_price,
        'booking': booking,
    }
    return render(request, 'customer/refund.html', context)


@login_required
def check_refund_status(request, booking_id):
    customer = get_object_or_404(Customer, user=request.user)
    booking = get_object_or_404(Booking, id=booking_id, customer=customer)

    refund_requested = RefundRequest.objects.filter(booking=booking).exists()

    return JsonResponse({'refund_requested': refund_requested})


@login_required
def profile(request):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'User not authenticated'}, status=401)

    try:
        customer = Customer.objects.get(user=request.user)
    except Customer.DoesNotExist:
        customer = None

    bookings = Booking.objects.filter(customer=customer) if customer else []

    if request.method == 'POST':
        user_form = UserProfileForm(request.POST, instance=request.user)
        profile_form = CustomerProfileForm(request.POST, request.FILES, instance=customer)
        password_form = CustomPasswordChangeForm(user=request.user, data=request.POST)

        if 'update_profile' in request.POST:
            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                return JsonResponse({'status': 'success', 'message': 'Profile updated successfully.'})
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': {
                        'profile_errors': profile_form.errors.as_json(),
                        'user_errors': user_form.errors.as_json(),
                    }
                })

        elif 'change_password' in request.POST:
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                return JsonResponse({'status': 'success', 'message': 'Password changed successfully.'})
            else:
                return JsonResponse({
                    'status': 'error', 'message': {'password_errors': password_form.errors.as_json()}
                })

        return JsonResponse({'status': 'error', 'message': 'Invalid form submission'})

    user_form = UserProfileForm(instance=request.user)
    profile_form = CustomerProfileForm(instance=customer) if customer else CustomerProfileForm()
    password_form = CustomPasswordChangeForm(user=request.user)

    return render(request, 'customer/profile.html', {
        'user': request.user,
        'customer': customer,
        'bookings': bookings,
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
    })

@csrf_exempt 
@login_required
def update_profile_picture(request):
    if request.method == 'POST' and request.FILES.get('profile_picture'):
        try:
            customer = Customer.objects.get(user=request.user)  # Fetch the related Customer
            profile_picture = request.FILES['profile_picture']

            # Update the profile picture field
            customer.profile_picture = profile_picture
            customer.save()

            return JsonResponse({'success': True, 'url': customer.profile_picture.url})
        except Customer.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Customer profile not found'}, status=404)
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

@login_required
def booking_history(request):
    try:
        # Get the logged-in user's corresponding Customer object
        customer = Customer.objects.get(user=request.user)
        # Fetch all booking history for the customer, including canceled ones
        bookings = CustomerBooking.objects.filter(customer=customer).select_related('booking', 'cruise')
    except Customer.DoesNotExist:
        bookings = []  # If no customer object exists for the user, return an empty list

    context = {
        'bookings': bookings,
    }
    return render(request, 'customer/booking_history.html', context)

@login_required
def loyalty_program(request):
    return render(request, 'customer/loyalty_program.html')

@login_required
def feedback_view(request):
    try:
        # Get the currently logged-in user's customer instance
        customer = Customer.objects.get(user=request.user)
    except Customer.DoesNotExist:
        messages.error(request, "No associated customer profile found.")
        return redirect('profile')  # Redirect to the profile page or any relevant page

    # Fetching the list of cruises for the dropdown
    cruises = Cruise.objects.all()

    if request.method == 'POST':
        form = FeedbackForm(request.POST)

        # Validating and saving the feedback
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.customer = customer  # Link the feedback to the logged-in customer
            feedback.save()

            # Success message
            messages.success(request, "Your feedback has been submitted!")

            return redirect('feedback_reviews')  # Redirect to feedback page after submission

    else:
        # If it's a GET request, just display an empty form
        form = FeedbackForm()

    # Fetching all feedbacks to display
    feedbacks = Feedback.objects.all()

    context = {
        'form': form,
        'cruises': cruises,  # Pass the list of cruises for the dropdown
        'feedbacks': feedbacks  # Pass the list of feedbacks to show on the page
    }

    return render(request, 'customer/feedback.html', context)


@login_required
def itinerary(request):
    return render(request, 'customer/itinerary.html')

def special_request_view(request):
    try:
        # Get the currently logged-in user's customer instance
        customer = Customer.objects.get(user=request.user)
    except Customer.DoesNotExist:
        messages.error(request, "No associated customer profile found.")
        return redirect('profile')  # Redirect to a relevant page, e.g., profile page

    if request.method == "POST":
        form = SpecialRequestForm(request.POST)
        if form.is_valid():
            special_request = form.save(commit=False)  # Create object but don't save to DB yet
            special_request.customer = customer  # Link to the customer instance
            special_request.save()  # Save to the database
            messages.success(request, "Special request submitted successfully!")
            return redirect('profile')  # Redirect to a success page
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = SpecialRequestForm()

    return render(request, 'customer/special_request.html', {'form': form})
