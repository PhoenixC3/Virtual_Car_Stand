from locust import HttpUser, task

class TestCompanies(HttpUser):
    def on_start(self):
        """Initialize the user session with authentication"""
        # Login as a company
        login_data = {
            "type": "company",
            "email": "magma.doe@example5.com",
            "password": "Password123"
        }
        
        response = self.client.post(
            "/login",
            json=login_data,
            name="Company Login"
        )
        
        if response.status_code != 200:
            print(f"Failed to login: {response.text}")
            return

    @task
    def get_companies(self):
        """Test GET /companies endpoint"""
        self.client.get("/companies")