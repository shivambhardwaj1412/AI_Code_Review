# AI_Code_Review
AI-Powered Code Review &amp; Bug Detection Agent

#git checkout -b feature/add-vulnerable-code
git add vulnerable_pr.py
git commit -m "Add vulnerable code for review demo"
git push origin feature/add-vulnerable-code

# Terminal 1
python -m venv venv 
.\venv\Scripts\Activate.ps1  
python start_server.py      

# Terminal 2
git checkout -b feature/add-vulnerable-code