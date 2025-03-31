# Acato 2

This is a first try at a comprehensive solution to help Acato Information Management rapidly assess potential business leads from third parties submitting Requests for Information (RFI) or Requests for Proposal (RFP). This repository contains a FastAPI backend (Python) and a Next.js/React frontend.

---

## Overview

- **Backend:** FastAPI (Python) for document classification and processing.
- **Frontend:** Next.js/React for a user-friendly interface.
- **Environment Management:** Python virtual environment (venv) for backend dependencies and Node.js for frontend packages.

---

## System Requirements

### Backend (FastAPI)
- **Python 3.11.8** (or higher)
- **Pip** (Python package manager)
- **Virtual Environment** (venv)

### Frontend (React/Next.js)
- **Node.js** (LTS version recommended, e.g. Node 16 or Node 18)
- **npm** (Node package manager)

### Additional Tools (Both macOS and Windows)
- **Git:** For cloning and managing the repository.

---

## Installation

### 1. Clone the Repository

Clone the repo to your local machine:

```bash
git clone https://github.com/eliasbrown99/Capstone.git
cd Capstone
```
### 2. Set Up the Python Environment

__Create a Virtual Environment:__

```bash
python -m venv venv
```
__Activate the Virtual Environment:__

* __macOS/Linux:__
  ```bash
  source venv/bin/activate
  ```

* __Windows (Command Prompt):__
  ```cmd
  venv\Scripts\activate
  ```
* __Windows (PowerShell):__
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
  *If you receive an execution policy error, run:*
  ```powershell
  Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```
__Install Python Dependencies:__

With the virtual environment activated, run:
```bash
pip install -r requirements.txt
```

### 3. Install Node.js and Git

#### For macOS:
- **Node.js:**  
  - Option 1: Download the latest LTS version from [nodejs.org](https://nodejs.org/) and follow the installer instructions.  
  - Option 2: If you have Homebrew installed, run:
    ```bash
    brew install node
    ```
- **Git:**  
  - Option 1: Download and install Git from [git-scm.com](https://git-scm.com/).  
  - Option 2: If you have Homebrew installed, run:
    ```bash
    brew install git
    ```

#### For Windows:
- **Node.js:**  
  - Download the latest LTS version from [nodejs.org](https://nodejs.org/) and run the installer.
- **Git:**  
  - Download the installer from [git-scm.com](https://git-scm.com/download/win) and follow the installation instructions.




### 4. Set Up the React Frontend
Navigate to the frontend directory:
```bash
cd solicitation-frontend
```
Install Node.js dependencies:
```bash
npm install
```
### 5. Create the .env file

Create a file named ```.env``` in the root directory ```Capstone``` of the project (the same one containing ```requirements.txt``` and ```SolicitationClassification.py```). You can do this manually or cd into the directory and use 

```bash
touch .env
```
Inside ```.env```, add your OpenAI API key (request it from Elias):

```bash
OPEN_API_KEY=sk-xxxxx
MODEL_PATH=./models
DATA_PATH=./data
```

## Running the Applicatoins
### Start the FastAPI Backend
Ensure your virtual environment is activated, then start the backend:
```bash
python -m app.main
```
or
```bash
uvicorn SolicitationClassification:app --reload
```
### Start the React Frontend
Open a new terminal window (or tab), navigate to the ```solicitation-frontend``` folder,
and run:
```bash
npm run dev
```
This starts the Next.js development server, which can be opened in web browser (http://localhost:3000).
_Tip:_ Opening two terminal windows - one for the backend and one for the frontend will be useful.

## File Structure
```bash
.
├── app/                     # Application logic (controllers, services)
├── config/                  # Configuration files
├── data/                    # Data files (CSVs, seeds, etc.)
├── models/                  # Database models or ORM files
├── solicitation-frontend/   # React/Next.js frontend
│   ├── components/
│   │   ├── SolicitationDashboard.jsx
│   │   └── modules/         # Reusable UI components/modules
│   ├── pages/
│   │   ├── _app.js
│   │   ├── _document.js
│   │   └── index.js
│   ├── public/              # Static assets (images, icons)
│   ├── .eslintrc.json
│   ├── .gitignore
│   ├── .prettierrc
│   ├── package.json
│   ├── package-lock.json
│   ├── postcss.config.mjs
│   ├── README.md
│   └── tailwind.config.mjs
├── venv/                    # Python virtual environment (local)
├── .env                     # Environment variables for Python/Node
├── .gitattributes
├── .gitignore
├── requirements.txt         # Python dependencies
└── SolicitationClassification.py  # FastAPI application entry point
```
## Usage
* __Backend:__
  * Run the FastAPI server using uvicorn or by running ```SolicitationClassification.py``` directly.
  * Use the endpoints defined in ```SolicitationClassification.py```for document classifcation.

* __Frontend:__
  * Interact with the application via browser at http://localhost:3000.

* __Stopping the Applications:__
  * Press ```Ctrl + C``` in the terminal where the application is running.

## Troubleshooting

* __Virtual Environment Activation (Windows PowerShell):__

    If you see an execution policy error, run:
    ```powershell
    Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
    ```
    and then activate your virtual environment again.
    
* __System Dependencies:__

    Ensure that Python, Node.js, and Git are properly installed on your system

