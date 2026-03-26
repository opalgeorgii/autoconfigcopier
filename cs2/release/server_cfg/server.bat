:: Add validate after 730 if validation is needed
steamcmd\steamcmd.exe +force_install_dir ../server/ +login anonymous +app_update 730 +quit

:: Navigate to server executable
cd server\game\bin\win64

:: Start the server using your Game Server token and prevent DLL preloading
:: Replace +map de_mirage with +host_workshop_map <map_id> if you want to use a workshop map
start cs2.exe -dedicated -usercon -console -secure -serverlogging -DoNotPreloadDLLs ^
+game_type 0 +game_mode 1 ^
+map de_mirage ^
+sv_logfile 1 ^
+sv_setsteamaccount <your_game_server_token> ^
+exec server.cfg