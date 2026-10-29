CREATE TABLE customers (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(120) NOT NULL,
  region VARCHAR(80) NOT NULL,
  created_at DATE NOT NULL
);

CREATE TABLE products (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(120) NOT NULL,
  category VARCHAR(80) NOT NULL,
  price DECIMAL(10, 2) NOT NULL
);

CREATE TABLE orders (
  id INT PRIMARY KEY AUTO_INCREMENT,
  customer_id INT NOT NULL,
  product_id INT NOT NULL,
  quantity INT NOT NULL,
  order_date DATE NOT NULL,
  FOREIGN KEY (customer_id) REFERENCES customers(id),
  FOREIGN KEY (product_id) REFERENCES products(id)
);

INSERT INTO customers (name, region, created_at) VALUES
  ('Aarav Shah', 'West', '2025-01-14'),
  ('Mira Iyer', 'South', '2025-02-02'),
  ('Kabir Rao', 'North', '2025-03-11'),
  ('Anaya Das', 'East', '2025-04-05');

INSERT INTO products (name, category, price) VALUES
  ('Trail Backpack', 'Outdoors', 79.00),
  ('Insulated Bottle', 'Outdoors', 24.50),
  ('Desk Lamp', 'Home', 48.00),
  ('Wireless Mouse', 'Electronics', 35.00);

INSERT INTO orders (customer_id, product_id, quantity, order_date) VALUES
  (1, 1, 2, '2025-05-10'),
  (1, 2, 3, '2025-05-12'),
  (2, 3, 1, '2025-05-16'),
  (2, 4, 2, '2025-06-03'),
  (3, 1, 1, '2025-06-09'),
  (3, 3, 2, '2025-06-15'),
  (4, 2, 4, '2025-07-01'),
  (4, 4, 1, '2025-07-05');

