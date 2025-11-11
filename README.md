# 📚 Library Tracking System

Welcome to the **Library Tracking System**! This project is a comprehensive application built with **Python**, **Django**, **Django REST Framework (DRF)**, and **Celery**. It manages authors, books, members, and loans within a library context. The application is fully containerized using **Docker**, allowing for easy setup and deployment.

---

## 📌 **Project Overview**
This application enables **library tracking** by allowing users to manage authors, books, members, and loans efficiently.

### **Tech Stack**
- **Python 3.9** – Backend development.
- **Django 4.2** – Web framework.
- **Django REST Framework** – API development.
- **Celery 5.3** – Task queue for async jobs.
- **Redis 6** – Message broker for Celery.
- **PostgreSQL 13** – Database.
- **Docker & Docker Compose** – Containerized setup.

---

## 🛠 **Setup Instructions**

### 1️⃣ **Clone the Repository**
```sh
git clone https://gitlab.com/search-atlas-interviews/django-library-tracking-system
cd django-library-tracking-system
```

### 2️⃣ **Configure Your Git Remote**
To work with your own repository, you need to replace the default remote with one you control. We recommend using **GitHub** for this, it's free.

#### 🏗 **Create an Empty Public Repository on GitHub**
1. Go to [GitHub](https://github.com/) and sign in.
2. Click on the **+** in the top-right corner and select **New repository**.
3. Enter a repository name (e.g., `django-library-tracking-system`).
4. Choose **Public**.
5. **Do not** initialize with a README, `.gitignore`, or license.
6. Click **Create repository**.
7. Copy the repository URL (it should look like `https://github.com/your-username/your-repo.git`).

#### 🔧 **Replace the Default Git Remote**
Run the following commands to rename the existing remote and add your newly created repository:

```sh
git remote rename origin upstream
git remote add origin [YOUR_GITHUB_REPOSITORY_URL]
git push -u origin main
```

### 3️⃣ **Create a `.env` File**
Create a `.env` file in the root directory to store environment variables:
```sh
touch .env
```

#### 📌 **Content of `.env`**
```env
DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost 127.0.0.1 [::1]
DATABASE_URL=postgres://library_user:library_password@db:5432/library_db
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
SECRET_KEY=your-secret-key
DEFAULT_FROM_EMAIL=admin@library.com
```
> **Note:** Replace `your-secret-key` with a secure key. Ensure that `.env` is included in `.gitignore`.

### 4️⃣ **Build and Run Docker Containers**
```sh
docker-compose build
docker-compose up
```
This command will:
- Start PostgreSQL (`db`) and Redis (`redis`) services.
- Build and run the Django application (`web`).
- Run the Celery worker (`celery`).
- Run the Celery Beat scheduler (`celery-beat`).

### 5️⃣ **Initialize the Django Project**
Apply migrations and create a superuser:
```sh
docker-compose run web python manage.py makemigrations
docker-compose run web python manage.py migrate
docker-compose run web python manage.py migrate django_celery_beat
docker-compose run web python manage.py createsuperuser
```
Follow the prompts to create a superuser account.

### 6️⃣ **Start the Application**
```sh
docker-compose up
```
To stop the running containers, press `CTRL+C` in the terminal where `docker-compose up` is running, then execute:
```sh
docker-compose down
```

---

## 📂 **Project Structure**
```plaintext
django-library-tracking-system/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env
├── .gitignore
├── manage.py
├── library_system/
│   ├── __init__.py
│   ├── asgi.py
│   ├── celery.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── library/
    ├── __init__.py
    ├── admin.py
    ├── apps.py
    ├── models.py
    ├── serializers.py
    ├── tasks.py
    ├── tests.py
    └── views.py
```

---

## 📌 **Accessing the Application**

### 🔑 **Django Admin Interface**
- **URL:** [http://localhost:8000/admin/](http://localhost:8000/admin/)
- **Login:** Use the superuser credentials you created.
- **Functionality:** Manage authors, books, members, loans, and scheduled Celery tasks through the admin panel.

### 📌 **Core API Endpoints**
| Method | Endpoint          | Description |
|--------|------------------|-------------|
| `GET`  | `/api/authors/`  | Fetch all authors |
| `GET`  | `/api/books/`    | Fetch all books |
| `GET`  | `/api/members/`  | Fetch all members |
| `GET`  | `/api/loans/`    | Fetch all loans |
| `POST` | `/api/authors/`  | Create a new author |
| `POST` | `/api/books/`    | Create a new book |
| `POST` | `/api/members/`  | Create a new member |
| `POST` | `/api/loans/`    | Create a new loan |
| `POST` | `/api/books/{id}/loan/` | Loan a book to member |
| `POST` | `/api/books/{id}/return_book/` | Return a loaned book |

### 🔄 **Background Task Endpoints**
| Method | Endpoint          | Description |
|--------|------------------|-------------|
| `POST` | `/api/tasks/overdue-reminders/` | Trigger overdue book reminders |
| `POST` | `/api/tasks/monthly-report/` | Generate monthly statistics report |
| `POST` | `/api/tasks/inventory-check/` | Check for low inventory books |
| `POST` | `/api/tasks/fetch-metadata/` | Fetch book metadata from external API |
| `POST` | `/api/loans/batch_return/` | Batch process loan returns |

📖 **For detailed API documentation, see [API_DOCUMENTATION.md](API_DOCUMENTATION.md)**

---

## 🧪 **Testing & Code Quality**

### Run Tests
```sh
# Run all tests
make test
# or
pytest

# Run with coverage
make coverage
# or
pytest --cov=library --cov=library_system --cov-report=html
```

### Code Quality Checks
```sh
# Run all quality checks (lint + format + isort)
make quality

# Individual checks
make lint          # Flake8 linting
make format        # Black formatting
make isort         # Import sorting
```

### Install Pre-commit Hooks
```sh
make install-dev
# or
pre-commit install
```

---

## 🔄 **Celery Background Tasks**

This application uses Celery for asynchronous task processing:

### Automated Scheduled Tasks
- **Daily**: Send overdue book reminders (14+ day grace period)
- **Weekly**: Check and alert for low inventory books
- **Monthly**: Generate library statistics report
- **Monthly**: Clean up old returned loan records

### On-Demand Tasks
- Email notifications when books are loaned
- Fetch book metadata from Google Books API
- Batch process loan returns
- Manual trigger of scheduled tasks via API

### Monitor Celery
```sh
# View active tasks
docker-compose exec celery celery -A library_system inspect active

# View scheduled tasks
docker-compose exec celery celery -A library_system inspect scheduled

# View Celery Beat logs
docker-compose logs celery-beat
```

---

## 📚 **Additional Documentation**

- **[API_DOCUMENTATION.md](API_DOCUMENTATION.md)** - Comprehensive API reference with examples
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Technical implementation details and architecture

---

## 🎯 **Key Features**

✅ RESTful API with Django REST Framework
✅ Async background task processing with Celery
✅ Scheduled periodic tasks with Celery Beat
✅ External API integration (Google Books)
✅ 80%+ test coverage with pytest
✅ Code quality enforcement (Flake8, Black, Isort)
✅ Pre-commit hooks for automated checks
✅ Docker containerization for easy deployment
✅ CI/CD pipeline with GitHub Actions
✅ Comprehensive documentation

---

## 🎯 **License**
This project is licensed under the **MIT License**.

---

🚀 **Happy coding!** 🎉