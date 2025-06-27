-- Create Tables
CREATE TABLE car (
    car_id SERIAL PRIMARY KEY,
    car_year INT NOT NULL,
    car_manufacturer VARCHAR(100) NOT NULL,
    car_model VARCHAR(100) NOT NULL,
    car_condition VARCHAR(50),
    car_cylinders VARCHAR(50),
    car_fuel VARCHAR(50),
    car_odometer INTEGER,
    car_transmission VARCHAR(50),
    car_vin VARCHAR(17) UNIQUE NOT NULL,
    car_drive VARCHAR(50),
    car_size VARCHAR(50),
    car_type VARCHAR(50),
    car_paint_color VARCHAR(50)
);

CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100),
    email VARCHAR(255) UNIQUE NOT NULL
);

CREATE TABLE meeting (
    meeting_id SERIAL PRIMARY KEY,
    client_id INT NOT NULL,
    schedule_date TIMESTAMP NOT NULL,
    meeting_status VARCHAR(60) CHECK (meeting_status IN ('StatusEnum_SCHEDULED', 'StatusEnum_COMPLETED', 'StatusEnum_CANCELED')) NOT NULL,
    FOREIGN KEY (client_id) REFERENCES users(user_id) ON DELETE CASCADE
);


CREATE TABLE maintenance (
    maintenance_id SERIAL PRIMARY KEY,
    maintenance_car_id INT NOT NULL,
    maintenance_type VARCHAR(60) CHECK (maintenance_type IN ('MaintenanceTypeEnum_BASIC', 'MaintenanceTypeEnum_FULL')) NOT NULL,
    maintenance_status VARCHAR(60) CHECK (maintenance_status IN ('MaintenanceStatusEnum_ONGOING', 'MaintenanceStatusEnum_FINISHED')) NOT NULL,
    maintenance_client_notes TEXT,
    maintenance_staff_notes TEXT,
    maintenance_cost DOUBLE PRECISION,
    maintenance_start_date TIMESTAMP NOT NULL,
    maintenance_end_date TIMESTAMP,
    FOREIGN KEY (maintenance_car_id) REFERENCES car(car_id) ON DELETE CASCADE
);

CREATE TABLE inspection (
    inspection_id SERIAL PRIMARY KEY,
    inspection_car_id INT NOT NULL,
    inspection_status VARCHAR(60) CHECK (inspection_status IN ('InspectionStatusEnum_ONGOING', 'InspectionStatusEnum_FINISHED')) NOT NULL,
    inspection_client_notes TEXT,
    inspection_staff_notes TEXT,
    inspection_cost DOUBLE PRECISION,
    inspection_start_date TIMESTAMP NOT NULL,
    inspection_end_date TIMESTAMP,
    FOREIGN KEY (inspection_car_id) REFERENCES car(car_id) ON DELETE CASCADE
);

CREATE TABLE car_listing (
    listing_id SERIAL PRIMARY KEY,
    listing_car_id INT NOT NULL,
    listing_user_id INT NOT NULL,
    listing_type VARCHAR(60) CHECK (listing_type IN ('TypeEnum_RENT', 'TypeEnum_BUY')) NOT NULL,
    listing_description TEXT,
    listing_posting_date TIMESTAMP NOT NULL,
    listing_sale_price DOUBLE PRECISION NOT NULL,
    listing_promoted BOOLEAN NOT NULL,
    listing_status VARCHAR(60) CHECK (listing_status IN ('StatusEnum_AVAILABLE', 'StatusEnum_RESERVED', 'StatusEnum_SOLD')) NOT NULL,
    FOREIGN KEY (listing_car_id) REFERENCES car(car_id) ON DELETE CASCADE,
    FOREIGN KEY (listing_user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE transaction (
    transaction_id SERIAL PRIMARY KEY,
    buyer_id INT NOT NULL,
    car_id INT NOT NULL,
    transaction_type VARCHAR(60) CHECK (transaction_type IN ('TypeEnum_RENT', 'TypeEnum_BUY')) NOT NULL,
    total_amount DOUBLE PRECISION NOT NULL,
    transaction_status VARCHAR(60) CHECK (transaction_status IN ('StatusEnum_PENDING', 'StatusEnum_COMPLETED', 'StatusEnum_CANCELED')) NOT NULL,
    transaction_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP,
    FOREIGN KEY (car_id) REFERENCES car(car_id) ON DELETE CASCADE,
    FOREIGN KEY (buyer_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Insert Dummy Users
INSERT INTO users (first_name, last_name, email) 
VALUES 
    ('Gabripel', 'Entites', 'gabriel.henriques@example.com'),
    ('Guilherme', 'Sousa', 'guilherme.s@example.com'),
    ('Manuel', 'Campos', 'manuel.campos@example.com'),
    ('Taigo', 'Almeida', 'taigo.almeida@example.com');

COPY car FROM '/docker-entrypoint-initdb.d/cars.csv' DELIMITER ',' CSV HEADER;
COPY car_listing FROM '/docker-entrypoint-initdb.d/listings.csv' DELIMITER ',' CSV HEADER;

-- Insert Dummy Maintenance Records
INSERT INTO maintenance (maintenance_car_id, maintenance_type, maintenance_status, maintenance_client_notes, maintenance_staff_notes, maintenance_cost, maintenance_start_date, maintenance_end_date)
VALUES 
    (1, 'MaintenanceTypeEnum_BASIC', 'MaintenanceStatusEnum_ONGOING', 'Oil change needed', 'Parts ordered', 50.00, '2024-03-25 10:00:00', NULL),
    (2, 'MaintenanceTypeEnum_FULL', 'MaintenanceStatusEnum_FINISHED', 'Brakes making noise', 'Replaced brake pads', 200.00, '2024-03-20 08:30:00', '2024-03-22 15:45:00'),
    (3, 'MaintenanceTypeEnum_BASIC', 'MaintenanceStatusEnum_FINISHED', 'General check-up', 'Everything OK', 75.00, '2024-03-18 09:15:00', '2024-03-18 12:00:00');

-- Insert Dummy Inspection Records
INSERT INTO inspection (inspection_car_id, inspection_status, inspection_client_notes, inspection_staff_notes, inspection_cost, inspection_start_date, inspection_end_date)
VALUES 
    (1, 'InspectionStatusEnum_ONGOING', 'Check engine light on', 'Diagnosing issue', 100.00, '2024-03-25 14:00:00', NULL),
    (2, 'InspectionStatusEnum_FINISHED', 'Check engine light on', 'Replaced spark plugs', 150.00, '2024-03-20 10:30:00', '2024-03-20 12:45:00'),
    (3, 'InspectionStatusEnum_FINISHED', 'Check engine light on', 'Replaced air filter', 50.00, '2024-03-18 14:30:00', '2024-03-18 16:00:00');

-- Insert Dummy Transactions
INSERT INTO transaction (buyer_id, car_id, transaction_type, total_amount, transaction_status, transaction_date, end_date) 
VALUES 
    (1, 1, 'TypeEnum_BUY', 25000.00, 'StatusEnum_COMPLETED', '2024-03-10 14:30:00', NULL),
    (2, 2, 'TypeEnum_RENT', 500.00, 'StatusEnum_PENDING', '2024-03-15 09:00:00', '2024-03-22 09:00:00'),
    (3, 3, 'TypeEnum_BUY', 32000.00, 'StatusEnum_PENDING', '2024-03-18 16:45:00', NULL);

-- Insert Dummy Meetings
INSERT INTO meeting (client_id, schedule_date, meeting_status)
VALUES 
    (1, '2024-03-12 10:00:00', 'StatusEnum_SCHEDULED'),
    (2, '2024-03-14 11:30:00', 'StatusEnum_COMPLETED'),
    (3, '2024-03-20 15:00:00', 'StatusEnum_CANCELED');