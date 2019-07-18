#!/usr/bin/env python3

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from sqlalchemy.orm import joinedload, subqueryload, subqueryload_all, joinedload_all

import sqlparse
import pygments
from pygments.lexers.sql import SqlLexer
from pygments.formatters.terminal import TerminalFormatter

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = True
db = SQLAlchemy(app)


def pretty_print_query(query):
    """
    Converts your SQLALchemy query object into pretty SQL Code
    """
    parsed_query = sqlparse.format(str(query), reindent=True)
    lexer = SqlLexer()
    formatter = TerminalFormatter(bg="dark")
    print(pygments.highlight(parsed_query, lexer, formatter))


class FoodTruck(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), index=True)
    __mapper_args__ = {"polymorphic_identity": "food_truck", "polymorphic_on": type}

    menu_items = db.relationship("MenuItem", back_populates="food_truck")
    employees = db.relationship("Employee", back_populates="food_truck")

    name = db.Column(db.String(80), unique=True, nullable=False)

    def __repr__(self):
        return f'<FoodTruck type={self.type} id={self.id} name="{self.name}">'


class TacoTruck(FoodTruck):

    id = db.Column(db.Integer, db.ForeignKey("food_truck.id"), primary_key=True)
    __mapper_args__ = {"polymorphic_identity": "taco_truck"}


class Person(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), index=True)
    __mapper_args__ = {"polymorphic_identity": "person", "polymorphic_on": type}

    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))

    @property
    def name(self):
        return f"{self.last_name or 'NA'}, {self.first_name or 'NA'}"


class Employee(Person):

    id = db.Column(db.Integer, db.ForeignKey("person.id"), primary_key=True)

    __mapper_args__ = {"polymorphic_identity": "employee"}

    food_truck_id = db.Column(db.Integer, db.ForeignKey("food_truck.id"))
    food_truck = db.relationship(FoodTruck, back_populates="employees")

    orders_served = db.relationship("Order", back_populates="employee")


class Customer(Person):

    id = db.Column(db.Integer, db.ForeignKey("person.id"), primary_key=True)

    __mapper_args__ = {"polymorphic_identity": "customer"}
    orders_requested = db.relationship("Order", back_populates="customer")


menu_item_orders = db.Table(
    "menu_item_orders",
    db.Model.metadata,
    db.Column("menu_item_id", db.Integer, db.ForeignKey("menu_item.id")),
    db.Column("order_id", db.Integer, db.ForeignKey("order.id")),
)


class MenuItem(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    price = db.Column(db.Integer)  # cents
    name = db.Column(db.String(50))

    # has many Orders
    # has many employees through orders (everyone who has sold this menu item)
    # not shared between different food trucks (belongs_to food truck)

    food_truck_id = db.Column(db.Integer, db.ForeignKey("food_truck.id"))
    food_truck = db.relationship(FoodTruck, back_populates="menu_items")

    orders = db.relationship("Order", secondary=menu_item_orders)


class Order(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"))
    employee = db.relationship("Employee", back_populates="orders_served")

    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"))
    customer = db.relationship("Customer", back_populates="orders_requested")

    menu_items = db.relationship("MenuItem", secondary=menu_item_orders)


def main():

    db.create_all()

    taco_truck = TacoTruck(
        name="Hell's Chariot",
        menu_items=[
            MenuItem(name="Super Burrito", price=10_00),
            MenuItem(name="California Burrito", price=7_00),
            MenuItem(name="Shrimp Burrito", price=8_00),
        ],
        employees=[
            Employee(first_name="Danny", last_name="Zuko"),
            Employee(first_name="Sandra", last_name="Dee"),
        ],
    )

    db.session.add(taco_truck)
    db.session.commit()

    customer = Customer(first_name="Frenchy")

    db.session.add(customer)
    db.session.commit()

    orders = [
        Order(
            menu_items=[taco_truck.menu_items[0], taco_truck.menu_items[1]],
            customer=customer,
            employee=taco_truck.employees[0],
        ),
        Order(
            menu_items=[taco_truck.menu_items[1]],
            customer=customer,
            employee=taco_truck.employees[1],
        ),
    ]

    db.session.add_all(orders)
    db.session.commit()

    # let's try some crazy joining

    # for each customer, join their orders, the orders' employee taco trucks and employees
    # and do it eagerly

    query = (
        db.session.query(Order)
        .join(Order.menu_items)
        .join(MenuItem.food_truck)
        .options(
            joinedload(Order.menu_items),
            joinedload(Order.customer),
            joinedload(Order.employee).joinedload(Employee.food_truck),
        )
        .filter(MenuItem.price == 7_00)
    )

    pretty_print_query(query)

    results = query.all()

    print("-" * 25 + " STARTING " + "-" * 25)

    for order in results:
        for menu_item in order.menu_items:
            print(
                order.customer.name,
                menu_item.name,
                menu_item.price,
                order.employee.food_truck.name,
                order.employee.food_truck.type,
            )


if __name__ == "__main__":
    main()
