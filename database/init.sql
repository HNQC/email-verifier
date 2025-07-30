CREATE DATABASE hnqc_verification;
USE hnqc_verification;

CREATE TABLE verification_codes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    code VARCHAR(10) NOT NULL,
    created_at DATETIME NOT NULL,
    used TINYINT DEFAULT 0
);
