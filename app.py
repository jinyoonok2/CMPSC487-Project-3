from db_connection import get_db_connection
from flask import Flask, render_template, request, redirect, url_for, session

import os
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from bson import ObjectId

import webbrowser
from threading import Timer

connection = get_db_connection()
app = Flask(__name__)
app.secret_key = 'secret_key'


# Assuming you have separate functions to get the collections
tenants_collection = connection["tenants"]
staff_collection = connection["staff"]
managers_collection = connection["managers"]
maintenance_requests_collection = connection["maintenance_requests"]

# Ensure the 'images' folder exists
IMAGES_DIR = os.path.join(app.root_path, 'images')
os.makedirs(IMAGES_DIR, exist_ok=True)


@app.route('/')
def index():
    return redirect(url_for('login'))
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Check each collection for the user
        tenant = tenants_collection.find_one({'email': email, 'password': password})
        staff = staff_collection.find_one({'email': email, 'password': password})
        manager = managers_collection.find_one({'email': email, 'password': password})

        if tenant:
            session['user_id'] = str(tenant['_id'])
            session['user_role'] = 'tenant'
            return redirect(url_for('home_tenant'))
        elif staff:
            session['user_id'] = str(staff['_id'])
            session['user_role'] = 'staff'
            return redirect(url_for('home_staff'))
        elif manager:
            session['user_id'] = str(manager['_id'])
            session['user_role'] = 'manager'
            return redirect(url_for('home_manager'))
        else:
            return redirect(url_for('login'))

    return render_template('login.html')

# Define the home routes for tenant, staff, and manager
@app.route('/home-tenant')
def home_tenant():
    if 'user_id' not in session or session['user_role'] != 'tenant':
        return redirect(url_for('login'))

    # When querying the database
    tenant_id = ObjectId(session['user_id'])
    tenant_info = tenants_collection.find_one({'_id': tenant_id})

    # Debug: Print the tenant information to the console
    print("Tenant Info:", tenant_info)

    if tenant_info:
        return render_template('home_tenant.html', tenant=tenant_info)
    else:
        return redirect(url_for('login'))

@app.route('/home-staff')
def home_staff():
    if 'user_id' not in session or session['user_role'] != 'staff':
        return redirect(url_for('login'))

    staff_id = ObjectId(session['user_id'])
    staff_info = staff_collection.find_one({'_id': staff_id})

    if staff_info:
        return render_template('home_staff.html', staff=staff_info)
    else:
        return redirect(url_for('login'))

@app.route('/home-manager')
def home_manager():
    if 'user_id' not in session or session['user_role'] != 'manager':
        return redirect(url_for('login'))

    manager_id = ObjectId(session['user_id'])
    manager_info = managers_collection.find_one({'_id': manager_id})

    if manager_info:
        return render_template('home_manager.html', manager=manager_info)
    else:
        return redirect(url_for('login'))

@app.route('/logout', methods=['POST'])
def logout():
    # Clear the user's session
    session.clear()
    # Redirect to the login page
    return redirect(url_for('login'))


@app.route('/tenant-submit-request', methods=['GET'])
def tenant_submit_request():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Retrieve the tenant's information from the database
    tenant_id = ObjectId(session['user_id'])
    tenant_info = tenants_collection.find_one({'_id': tenant_id})

    if tenant_info:
        # Render the form with the tenant's information
        return render_template('tenant_submit_request.html', tenant_info=tenant_info)
    else:
        return redirect(url_for('login'))

# Route for tenants to submit maintenance requests
@app.route('/submit-maintenance-request', methods=['POST'])
def submit_maintenance_request():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    tenant_id = request.form['tenantID']
    apartment_number = request.form['apartmentNumber']
    problem_area = request.form['problemArea']
    description = request.form['description']
    request_date = datetime.utcnow().strftime('%Y-%m-%d')  # Current date in YYYY-MM-DD format
    status = 'pending'
    photo_path = ''

    # Handle file upload
    photo = request.files['photo']
    if photo and allowed_file(photo.filename):
        filename = secure_filename(photo.filename)
        save_path = os.path.join(IMAGES_DIR, filename)
        photo.save(save_path)
        photo_path = f'images/{filename}'

    # Create document for the maintenance request
    maintenance_request = {
        "tenantID": tenant_id,
        "apartmentNumber": apartment_number,
        "problemArea": problem_area,
        "description": description,
        "requestDate": request_date,
        "status": status,
        "photo": photo_path
    }

    # Insert the new maintenance request document into the database
    maintenance_requests_collection.insert_one(maintenance_request)

    return redirect(url_for('home_tenant'))


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}


@app.route('/staff-view-requests', methods=['GET'])
def staff_view_requests():
    # existing search parameters
    apartment_number = request.args.get('apartment_number', '')
    problem_area = request.args.get('problem_area', '')
    status = request.args.get('status', '')

    # Default date values
    default_end_date = datetime.utcnow() + timedelta(days=1)  # Tomorrow
    default_start_date = default_end_date - timedelta(weeks=52)  # One year before

    # Retrieve start and end date parameters or use defaults
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    # Convert dates to datetime objects or use default
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else default_start_date
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else default_end_date

    # Build query based on search parameters
    query = {}
    if apartment_number:
        query['apartmentNumber'] = apartment_number
    if problem_area:
        query['problemArea'] = problem_area
    if status:
        query['status'] = status

    # Add date range to query only if dates are provided
    if start_date_str or end_date_str:
        query['requestDate'] = {
            '$gte': start_date.strftime('%Y-%m-%d'),
            '$lte': end_date.strftime('%Y-%m-%d')
        }

    # Fetch requests from the database based on the query
    requests = maintenance_requests_collection.find(query)

    return render_template('staff_view_request.html', requests=requests)


@app.route('/complete-maintenance-request', methods=['POST'])
def complete_maintenance_request():
    if 'user_id' not in session or session['user_role'] != 'staff':
        return redirect(url_for('login'))

    request_id = request.form.get('request_id')

    # Update the status in the database
    if request_id:
        maintenance_requests_collection.update_one(
            {'_id': ObjectId(request_id)},
            {'$set': {'status': 'completed'}}
        )

    return redirect(url_for('staff_view_requests'))

@app.route('/manager-view-tenants', methods=['GET'])
def manager_view_tenants():
    tenants = tenants_collection.find({})
    return render_template('manager_view_tenants.html', tenants=tenants)

@app.route('/manager-update-tenant', methods=['GET'])
def manager_update_tenant():
    tenant_id = request.args.get('tenant_id')
    if tenant_id:
        tenant = tenants_collection.find_one({'_id': ObjectId(tenant_id)})
        mode = "Edit"
    else:
        tenant = {}
        mode = "Create"

    # Prepare tenant fields for the form
    tenant_fields = {
        'name': tenant.get('name', ''),
        'phone_number': tenant.get('phoneNumber', ''),
        'email': tenant.get('email', ''),
        'check_in_date': tenant.get('checkInDate', ''),
        'check_out_date': tenant.get('checkOutDate', ''),
        'apartment_number': tenant.get('apartmentNumber', '')
    }

    return render_template('manager_update_tenants.html', tenant=tenant, mode=mode, tenant_fields=tenant_fields)

@app.route('/submit-tenant-form', methods=['POST'])
def submit_tenant_form():
    tenant_id = request.form.get('tenant_id')
    tenant_data = {
        'name': request.form.get('name'),
        'phoneNumber': request.form.get('phone_number'),
        'email': request.form.get('email'),
        'checkInDate': request.form.get('check_in_date'),
        'checkOutDate': request.form.get('check_out_date'),
        'apartmentNumber': request.form.get('apartment_number')
    }

    if tenant_id:
        # Update existing tenant
        tenants_collection.update_one({'_id': ObjectId(tenant_id)}, {'$set': tenant_data})
    else:
        # Create new tenant
        tenants_collection.insert_one(tenant_data)

    return redirect(url_for('manager_view_tenants'))

@app.route('/delete-tenant', methods=['POST'])
def delete_tenant():
    tenant_id = request.form.get('tenant_id')
    if tenant_id:
        tenants_collection.delete_one({'_id': ObjectId(tenant_id)})
    return redirect(url_for('manager_view_tenants'))

# Function to open the browser
def open_browser():
    webbrowser.open_new('http://127.0.0.1:5000/')

if __name__ == '__main__':
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        Timer(1, lambda: webbrowser.open_new('http://127.0.0.1:5000/')).start()
    app.run(debug=True)