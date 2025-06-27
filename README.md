# StandFCOOL Virtual Car Dealership System

# Chosen Dataset

https://www.kaggle.com/datasets/austinreese/craigslist-carstrucks-data?resource=download

# Business Capabilities

1. Car Listing Management
2. Car Sales and Transactions
3. Meetings Scheduling
4. Car Maintenance
5. Car Periodic Inspection
6. Promoted listings

# Use cases

1. Buying a car
2. Renting a car
3. Returning a rented car
4. Exploring the car catalog
5. Scheduling a meeting for staff support
6. Accessing car details
7. Adding a car listing
8. Edit a car listing
9. Removing a car listing
10. Adding a listing to promoted listings
11. View Listing History
12. View Rental and Sales History
13. View Inspection and Maintenance Reports

# Application Architecture for StandFCOOL Car Dealership System

## Functional Requirements

## 1. Car Listing Management
### 1.1 Adding a Car Listing
- Users can add a car listing by providing details of a car (manufacturer, model, year, condition, etc) and the details of the listing (sale price, description).
- The system shall validate required fields and reject incomplete submissions.
- The listing shall be assigned a unique `listingId`.

### 1.2 Editing a Car Listing
- Users can update their car listings to modify details like price, description, or status.
- The system shall validate any updates before applying changes.

### 1.3 Removing a Car Listing
- Users can remove their car listings as they wish.
- Deleted listings shall no longer be visible to buyers.
- The system shall not retain historical records of removed listings.

### 1.4 Viewing Car Listings
- Users can browse available cars via a paginated and filterable list.
- The system shall allow filtering by car details like such as manufacturer, model, year, condition, etc... 
- Each listing item shall display a description, sale price, posting date and a link to the full car listing page.

### 1.5 Viewing Specific Car Listing
- Users can click on a listing to view full car details, seller (user) information and initiate the purchase of the car.

### 1.6 Promoted Listings
- Users can promote their listings for increased visibility.
- The system shall flag promoted listings and display them in priority search results.

## 2. Car Sales and Transactions
### 2.1 Buying a Car
- Users can initiate a car purchase by selecting a listing and proceeding with a transaction.
- The system shall process payments and update the listing status to `sold` upon completion.
- The buyer and seller shall receive a confirmation notification.

### 2.2 Renting a Car
- Users can rent a car by selecting a listing and setting a rental period.
- The system shall verify rental availability before confirming the transaction.
- The system shall process payments and update the listing status to `reserved` upon completion.
- The buyer and seller shall receive a confirmation notification.

### 2.3 Returning a Rented Car
- Renters can mark a car as `returned` at the end of the rental period.
- The system shall verify the return status and update the listing accordingly.

### 2.4 Viewing Transaction History
- Users can view their past transactions, including purchase, rental, and return details.
- The system shall provide receipts and transaction status updates.

## 3. Car Maintenance
### 3.1 Scheduling Maintenance
- Car owners can schedule maintenance services (`basic`, `full`) and add beforehand notes to it.
- The system shall store maintenance requests along with the car details, setting the maintenance status to `Ongoing`.

### 3.2 Tracking Maintenance History
- Users can view a car’s past maintenance records.
- The system shall store details such as service date, type, cost, and mechanic notes.

### 3.3 Post-Maintenance
- When the car maintenance ends, a Staff User adds notes, the cost of it and sets it to `Finished`.
- The system shall store those details, add an end date and notify the car owner about it.

## 4. Car Periodic Inspection
### 4.1 Scheduling an Inspection
- Users can book a periodic inspection for their cars.
- The system shall notify users of upcoming inspection deadlines.

### 4.2 Viewing Inspection Reports
- Users can view a car’s past inspection reports, including findings and recommendations.

### 4.3 Post-Inspection
- When the car inspection ends, a Staff User adds notes, the cost of it and sets it to `Finished`.
- The system shall store those details, add an end date and notify the car owner about it.

## 5. Meeting for Staff Support
### 5.1 Scheduling a Meeting
- Users can book a meeting with the owner of the car in it's respective listing.
- The system shall allow selecting an available time slot.

### 5.2 Managing Meetings
- Users can reschedule or cancel meetings.
- The system shall track the meeting status (`scheduled`, `completed`, `canceled`).

# Architecture Description
The system follows a microservices architecture, with each service handling a specific domain. Microservices communicate between each other using gRPC, while external clients interact with the system via a REST-based API Gateway.

### API Gateway
- Acts as the single entry point for all external requests, by exposing a REST API.
- Receives HTTP REST requests and routes them to the appropriate microservices over gRPC
- Handles authentication and request validation.

### User Service
- Handles user registration, login.
- Manages user information (profile, settings).
- Stores user data in a dedicated database.

### Car Listing Service
- Manages car listings (add, update, delete).
- Stores and retrieve listing details.
- Updates Search Service for indexing.
- Interacts with the Transaction Service when a car is to be sold or rented.
- Uses a database to persist car listing data.

### Car Service
- Manages car details
- Uses a database to persist car data.

### Transaction Service
- Handles purchase and rental transactions.
- Interacts with the Car Listing Service to update listing status upon completion of a sale.
- Interacts with the Notification Service to notify the User about the transaction status.
- Stores transaction details in a database.

### Maintenance Service
- Schedules and manages maintenance appointments.
- Interacts with the Notification Service to notify the User about the maintenance status.
- Stores maintenance records in a database.

### Inspection Service
- Schedules and manages periodic car inspections appointments.
- Interacts with the Notification Service to notify the User of upcoming inspection deadlines and their status.
- Stores inspection records in a database.

### Meeting Service
- Schedules and manages meetings between users and dealership staff.
- Interacts with the Notification Service to notify the User of upcoming inspection deadlines and their status.
- Stores meeting details in a database.

### Notification Service
- Listens for gRPC requests from other services and notifies the User about each of them (transactions, maintenance status, etc...) via email or SMS.

### Search Service
- Indexes car listings for efficient searching and updates it when a listing is modified or added.
- Supports search filtering by attributes
- Retrieves search results and returns them to the API Gateway.

### Database Layer
- Some microservices have their own dedicated databases to ensure loose coupling and independent scaling. The types of databases will be determined based on the service's needs (structured for transactions, searchable for listings).

## Application Architecture Diagram in misc folder
