from django.contrib.auth import get_user_model
from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from core.models import UserModule, Customer, SpecialRequest, Feedback, Booking, OnboardService, Passenger, Payment
from django.contrib.auth.hashers import make_password
from django.forms import modelformset_factory
from core.models import Passenger

class CustomerSignupForm(forms.ModelForm):
    username = forms.CharField(required=True)
    email = forms.EmailField(required=True)
    password1 = forms.CharField(widget=forms.PasswordInput, required=True)
    password2 = forms.CharField(widget=forms.PasswordInput, required=True)

    class Meta:
        model = Customer
        fields = ['phone_number', 'address', 'date_of_birth', 'gender']

    def clean_password2(self):
        # Ensure both passwords match
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 != password2:
            raise forms.ValidationError("Passwords do not match")
        return password2

    def save(self, commit=True):
        # Create a new UserModule instance
        user_data = {
            'username': self.cleaned_data.get('username'),
            'email': self.cleaned_data.get('email'),
            'password': make_password(self.cleaned_data.get('password1')),
            'role': 'customer',
        }
        user = UserModule.objects.create(**user_data)

        # Create and associate a Customer instance with the new user
        customer = super().save(commit=False)
        customer.user = user

        if commit:
            user.save()
            customer.save()
        return customer


# Login Form for User
class LoginForm(forms.Form):
    username = forms.EmailField(label='Email')
    password = forms.CharField(widget=forms.PasswordInput)

# Customer Profile Form

User = get_user_model()

class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['phone_number', 'address', 'date_of_birth', 'gender']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email', 'username']

class CustomPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(widget=forms.PasswordInput, label='Old Password')
    new_password1 = forms.CharField(widget=forms.PasswordInput, label='New Password')
    new_password2 = forms.CharField(widget=forms.PasswordInput, label='Confirm New Password')

class SpecialRequestForm(forms.ModelForm):
    class Meta:
        model = SpecialRequest
        fields = ['request_type', 'details', 'priority_level']  # Include fields user can edit

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['cruise', 'rating', 'comments']
        
        # Customizing form labels and widgets
        labels = {
            'cruise': 'Select a Cruise',
            'rating': 'Rating (1-5)',
            'comments': 'Your Comments',
        }
        widgets = {
            'cruise': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Choose your cruise'}),
            'rating': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 5, 'placeholder': 'Rate the experience (1-5)', 'type': 'number'}),
            'comments': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Write your feedback here...', 'rows': 4}),
        }
    
    # Custom validation for rating field
    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        if not (1 <= rating <= 5):
            raise forms.ValidationError("Rating must be between 1 and 5.")
        return rating

    # Custom validation for comments field (optional: limit length)
    def clean_comments(self):
        comments = self.cleaned_data.get('comments')
        if len(comments) > 1000:
            raise forms.ValidationError("Your comments are too long. Please keep it under 1000 characters.")
        return comments

class BookingForm(forms.ModelForm):
    LOYALTY_LEVEL_CHOICES = [
        ('Gold', 'Gold'),
        ('Silver', 'Silver'),
        ('Bronze', 'Bronze'),
    ]

    loyalty_level = forms.ChoiceField(choices=LOYALTY_LEVEL_CHOICES, required=False)

    class Meta:
        model = Booking
        fields = [
            'cruise', 'room_type', 'travel_insurance', 
            'loyalty_program_member', 'loyalty_card_number', 
            'loyalty_pass', 'loyalty_level', 'number_of_passengers',
            'onboard_services'
        ]
        widgets = {
            'cruise': forms.Select(attrs={'class': 'booking-select'}),
            'room_type': forms.Select(attrs={'class': 'booking-select'}),
            'travel_insurance': forms.CheckboxInput(attrs={'class': 'booking-checkbox'}),
            'loyalty_program_member': forms.CheckboxInput(attrs={'class': 'booking-checkbox'}),
            'loyalty_card_number': forms.TextInput(attrs={'class': 'booking-input'}),
            'loyalty_pass': forms.TextInput(attrs={'class': 'booking-input'}),
            'loyalty_level': forms.Select(attrs={'class': 'booking-select'}),
            'number_of_passengers': forms.NumberInput(attrs={
                'class': 'booking-input', 
                'min': 1, 
                'id': 'number-of-passengers'
            }),
            'onboard_services': forms.CheckboxSelectMultiple(attrs={'class': 'booking-multiselect'}),
        }

class PassengerForm(forms.ModelForm):
    class Meta:
        model = Passenger
        fields = ['first_name', 'last_name', 'age', 'gender', 'passport_number', 'nationality']

PassengerFormSet = modelformset_factory(
    Passenger,
    form=PassengerForm,
    extra=1,  # Number of empty forms initially displayed
)


class PassengerForm(forms.ModelForm):
    class Meta:
        model = Passenger  # Replace with your actual model
        fields = ['first_name', 'last_name', 'age', 'gender', 'passport_number', 'nationality']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-field-input', 'placeholder': 'Enter first name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-field-input', 'placeholder': 'Enter last name'}),
            'age': forms.NumberInput(attrs={'class': 'form-field-input', 'placeholder': 'Enter age'}),
            'gender': forms.Select(attrs={'class': 'form-field-select'}),
            'passport_number': forms.TextInput(attrs={'class': 'form-field-input', 'placeholder': 'Enter passport number'}),
            'nationality': forms.TextInput(attrs={'class': 'form-field-input', 'placeholder': 'Enter nationality'}),
        }

# Optional: Formset for managing multiple PassengerForms
from django.forms import modelformset_factory

PassengerFormSet = modelformset_factory(
    Passenger,
    form=PassengerForm,
    extra=1  # Number of extra blank forms
)
