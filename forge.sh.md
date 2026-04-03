✅ Done — forge.sh created and working
The script is at /home/joe/repos/forge/forge.sh and supports:

Command	What it does
./forge.sh start [all]	Start postgres → redis → backend → frontend
./forge.sh stop [all]	Stop all services (kills by port)
./forge.sh restart backend	Restart a specific service
./forge.sh status	Show running/stopped status with PIDs
./forge.sh logs backend	Tail log file for a service
./forge.sh test	Run backend pytest + frontend typecheck
./forge.sh build	Production build frontend
./forge.sh db:migrate	Run Alembic migrations
./forge.sh db:reset	Drop + recreate + migrate database
Logs go to .logs/, PID files to .pids/ (both gitignored directories).

1