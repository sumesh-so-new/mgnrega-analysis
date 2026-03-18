import os
from dotenv import load_dotenv
load_dotenv()

HOST = os.getenv("HOST")
PORT = "5432"
DATABASE = os.getenv("DATABASE")
USER = os.getenv("USER")
PASSWORD = os.getenv("PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# import os
# from dotenv import load_dotenv
# load_dotenv()
# from streamlit import st

# HOST = os.getenv("HOST")
# PORT = os.getenv("PORT")
# DATABASE = os.getenv("DATABASE")
# USER = os.getenv("USER")
# PASSWORD = os.getenv("PASSWORD")
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# HOST = st.secrets["HOST"]
# PORT = "5432"
# DATABASE = st.secrets["DATABASE"]
# USER =  st.secrets["USER"]
# PASSWORD = st.secrets["PASSWORD"]
# OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
