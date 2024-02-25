import sqlalchemy as sq
from sqlalchemy.orm import sessionmaker
from models import create_tables, User, UserDictionary, MainDictionary
import configparser



def create_db(engine):

    main_words = (
        ('Mother', 'Мама'),
        ('Father', 'Папа'),
        ('Brother', 'Брат'),
        ('Sister', 'Сестра'),
        ('Grandmother', 'Бабушка'),
        ('Grandfather', 'Дедушка'),
        ('Uncle', 'Дядя'),
        ('Aunt', 'Тетя'),
        ('Son', 'Сын'),
        ('Daughter', 'Дочь'),
        ('Family', 'Семья'),
    )

    create_tables(engine)

    session = (sessionmaker(bind=engine))()

    for row in main_words:
        session.add(MainDictionary(word=row[0], translate=row[1]))
    session.commit()
    session.close()
    
config = configparser.ConfigParser()
config.read('settings.ini')

engine = sq.create_engine(config['postgres']['DSN'])

create_db(engine)