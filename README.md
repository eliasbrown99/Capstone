=====================================================
                    Acato 2
=====================================================

Overview
--------
A first attempt at assisting Acato Information Management (Acato) with designing a comprehensive software that assists their company with quickly and effectively assessing potential business leads from third parties who submit to Acato requests for information
(RFI) or requests for proposal (RFP).

Requirements
------------
- **Python**: 3.11.8 (or higher I presume)
- **Node.js/NPM**: [For running the React code]
- See the `requirements.txt` file for Python dependencies.

Installation
------------
1. **Clone the Repository:**
https://github.com/eliasbrown99/Capstone/


2. **Set Up the Python Environment:**
- Create a virtual environment:
  ```
  python -m venv venv
  ```
- Activate the virtual environment:
  - On Windows:
    ```
    venv\Scripts\activate
    ```
  - On macOS/Linux:
    ```
    source venv/bin/activate
    ```
- Install Python dependencies:
  ```
  pip install -r requirements.txt
  ```
3. **Set Up the React Environment:**
- Navigate to the folder containing your React code (if it’s in a separate directory, e.g., `solicitation-frontend`):
  ```
  cd solicitation-frontend
  ```
- Install Node dependencies:
  ```
  npm install
  ```
- Start the React application (if applicable):
  ```
  npm run dev 
  ```
  This will start the server and allow you to access it in browser at some localhost:X000

Usage
-----
- **Running the Python Code:**

 Run `SolicitationClassification.py' in the virtual environment venv. All dependencies should be included. You might need to install some system-wide packages with brew install ___
 
- **Interacting with the React App:**

 cd solicitation-frontend while in the virtual environment venv. Make sure you've already run npm install to install dependencies from package.json. Then npm run dev will allow you to interact with frontend in browser
 
ctrl + c to keyboard stop the programs inside terminal
you will need to open two terminals inside VSCode to run both scripts

File Structure
--------------
```
├── app/
│   └── ... (application logic / controllers / services)
├── config/
│   └── ... (configuration files)
├── data/
│   └── ... (data files / CSVs / seeds)
├── models/
│   └── ... (database models or ORM files)
├── solicitation-frontend/
│   ├── components/
│   │   ├── SolicitationDashboard.jsx
│   │   └── modules/
│   │       └── ... (reusable UI components / modules)
│   ├── pages/
│   │   ├── _app.js
│   │   ├── _document.js
│   │   └── index.js
│   ├── public/
│   │   └── ... (static assets like images or icons)
│   ├── .eslintrc.json
│   ├── .gitignore
│   ├── .prettierrc
│   ├── package.json
│   ├── package-lock.json
│   ├── postcss.config.mjs
│   ├── README.md
│   └── tailwind.config.mjs
├── venv/
│   └── ... (Python virtual environment)
├── .env               (environment variables for Python/Node)
├── .gitattributes
├── .gitignore
├── requirements.txt   (Python dependencies)
└── SolicitationClassification.py  (example Python script)
```
