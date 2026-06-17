import os
import logging
import click
from dotenv import load_dotenv

load_dotenv()

from app import create_app, db
from app.models import User

app = create_app(os.getenv('FLASK_ENV', 'default'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)


@app.cli.command('init-db')
def init_db_cmd():
    db.create_all()
    click.echo('Database initialized.')


@app.cli.command('reset-db')
def reset_db_cmd():
    db.drop_all()
    db.create_all()
    click.echo('Database reset.')


@app.cli.command('seed-data')
def seed_data_cmd():
    from init_db import seed_data
    seed_data()


@app.cli.command('create-admin')
@click.option('--username', prompt=True, help='Admin username')
@click.option('--email', prompt=True, help='Admin email')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Admin password')
def create_admin(username, email, password):
    existing = User.query.filter_by(username=username).first()
    if existing:
        click.echo(f'User "{username}" already exists.')
        return
    admin = User(username=username, email=email, is_admin=True)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    click.echo(f'Admin user "{username}" created.')


if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() in ('true', '1', 'yes')
    app.run(host=host, port=port, debug=debug)
