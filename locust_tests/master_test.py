from locust import HttpUser, task, between
from test_search import TestSearch
from test_companies import TestCompanies
from test_companies_specialties import TestCompaniesSpecialties
from test_job_postings_company import TestJobPostingsCompany

class MasterUser(HttpUser):
    wait_time = between(1, 3)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.search_test = TestSearch(self.environment)
        self.companies_test = TestCompanies(self.environment)
        self.companies_specialties_test = TestCompaniesSpecialties(self.environment)
        self.job_postings_test = TestJobPostingsCompany(self.environment)

    @task
    def run_search_test(self):
        self.search_test.test_search()

    @task
    def run_companies_test(self):
        self.companies_test.get_companies()

    @task
    def run_companies_specialties_test(self):
        self.companies_specialties_test.get_companies_specialities()

    @task
    def run_job_postings_test(self):
        self.job_postings_test.get_job_postings_company() 