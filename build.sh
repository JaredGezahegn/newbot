# build_files.sh
pip install -r requirements.txt
cp photo_2024-01-21_01-35-36.jpg staticfiles/admin-interface/logo/photo_2024-01-21_01-35-36.jpg
python3 manage.py collectstatic --no-input
