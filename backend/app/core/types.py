from sqlalchemy import TypeDecorator, Integer


class PrimaryKey(TypeDecorator):
    impl = Integer


class MoneyAmount(TypeDecorator):
    impl = Integer
