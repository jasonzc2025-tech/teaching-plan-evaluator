from dotenv import load_dotenv

load_dotenv()

from teaching_eval import create_app


application = create_app()
