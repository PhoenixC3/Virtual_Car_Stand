from locust import HttpUser, task
import random

class TestSearch(HttpUser):
    def on_start(self):
        """Initialize the user session with authentication"""
        # Login as a user
        login_data = {
            "type": "user",
            "email": "manuel@gmail.com",
            "password": "testemanel1"
        }
        
        response = self.client.post(
            "/login",
            json=login_data,
            name="User Login"
        )
        
        if response.status_code != 200:
            print(f"Failed to login: {response.text}")
            return

    @task
    def test_search(self):
        """Test GET /search endpoint with different queries"""
        # List of realistic search queries
        search_queries = [
            "software developer",
            "data scientist",
            "cloud engineer",
            "machine learning",
            "python developer",
            "frontend developer",
            "devops engineer",
            "full stack",
            "mobile app developer",
            "cybersecurity analyst"
        ]
        
        # Make a search request with a random query
        random_query = random.choice(search_queries)
        self.client.get(f"/search?query={random_query}")
