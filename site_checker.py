#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Site checker for Django - ASCII version for Python 3.6
"""

import os
import re
import sys
import time

PROJECT_ROOT = '/home/httpd/vhosts/tentoriumrb.ru/private/app/myapp'
sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myapp.settings')

# Try to initialize Django
try:
    import django
    django.setup()
    from django.conf import settings
    from django.urls import reverse, NoReverseMatch
    DJANGO_OK = True
    print("Django initialized successfully")
except Exception as e:
    print("Django init error:", str(e))
    DJANGO_OK = False

class SiteChecker:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.junk_files = []
        self.project_root = PROJECT_ROOT
        
    def check_templates(self):
        """Check Django templates"""
        print("\n--- Checking templates ---")
        
        if not DJANGO_OK:
            self.warnings.append("Django not available - skipping template check")
            return
            
        # Find template directories
        template_dirs = []
        try:
            if hasattr(settings, 'TEMPLATES') and settings.TEMPLATES:
                template_dirs = settings.TEMPLATES[0].get('DIRS', [])
        except:
            pass
            
        # Also check standard locations
        possible_dirs = [
            os.path.join(self.project_root, 'templates'),
            os.path.join(self.project_root, 'content', 'templates'),
        ]
        
        for dir_path in possible_dirs:
            if os.path.exists(dir_path) and dir_path not in template_dirs:
                template_dirs.append(dir_path)
        
        templates_count = 0
        for template_dir in template_dirs:
            if os.path.exists(template_dir):
                print("Checking directory:", template_dir)
                for root, dirs, files in os.walk(template_dir):
                    for file in files:
                        if file.endswith('.html'):
                            templates_count += 1
                            template_path = os.path.join(root, file)
                            self._check_template_file(template_path)
        
        print("Templates found:", templates_count)
    
    def _check_template_file(self, template_path):
        """Check single template file"""
        try:
            with open(template_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            rel_path = template_path.replace(self.project_root, '.')
            
            # Check URLs
            url_patterns = re.findall(r"{%\s*url\s+['\"]([^'\"]+)['\"]", content)
            for url_name in url_patterns:
                if DJANGO_OK:
                    try:
                        # Попробуем с параметрами по умолчанию
                        if url_name == 'article_detail':
                            reverse(url_name, kwargs={'pk': 1})
                        elif url_name == 'product_detail':
                            reverse(url_name, kwargs={'pk': 1})
                        elif url_name == 'category_products':
                            reverse(url_name, kwargs={'category_id': 1})
                        else:
                            reverse(url_name)
                    except NoReverseMatch:
                        self.errors.append("BAD URL in " + rel_path + ": " + url_name)
            
            # Check suspicious filters
            filter_patterns = re.findall(r"\|(\w+)", content)
            bad_filters = ['div', 'multiply', 'mod', 'subtract']
            for filter_name in filter_patterns:
                if filter_name in bad_filters:
                    self.warnings.append("SUSPICIOUS FILTER in " + rel_path + ": " + filter_name)
            
            # Check static files
            static_patterns = re.findall(r"{%\s*static\s+['\"]([^'\"]+)['\"]", content)
            for static_file in static_patterns:
                found = False
                if DJANGO_OK and hasattr(settings, 'STATICFILES_DIRS'):
                    for static_dir in settings.STATICFILES_DIRS:
                        static_path = os.path.join(static_dir, static_file)
                        if os.path.exists(static_path):
                            found = True
                            break
                
                if not found:
                    self.warnings.append("MISSING STATIC in " + rel_path + ": " + static_file)
                    
        except Exception as e:
            self.errors.append("TEMPLATE READ ERROR " + template_path + ": " + str(e))
    
    def check_static_files(self):
        """Check static files"""
        print("\n--- Checking static files ---")
        
        static_dirs = []
        if DJANGO_OK and hasattr(settings, 'STATICFILES_DIRS'):
            static_dirs = list(settings.STATICFILES_DIRS)
        
        possible_static = [
            os.path.join(self.project_root, 'static'),
            os.path.join(self.project_root, 'assets'),
        ]
        
        for path in possible_static:
            if os.path.exists(path) and path not in static_dirs:
                static_dirs.append(path)
        
        total_files = 0
        total_size = 0
        
        for static_dir in static_dirs:
            if os.path.exists(static_dir):
                print("Checking:", static_dir)
                for root, dirs, files in os.walk(static_dir):
                    for file in files:
                        total_files += 1
                        file_path = os.path.join(root, file)
                        
                        try:
                            size = os.path.getsize(file_path)
                            total_size += size
                            
                            if size > 5 * 1024 * 1024:  # >5MB
                                size_mb = size // (1024*1024)
                                self.warnings.append("LARGE FILE: " + file_path + " (" + str(size_mb) + "MB)")
                        except:
                            pass
        
        print("Static files:", total_files)
        print("Total size:", total_size // (1024*1024), "MB")
    
    def check_media_files(self):
        """Check media files"""
        print("\n--- Checking media files ---")
        
        media_dir = os.path.join(self.project_root, 'media')
        if DJANGO_OK and hasattr(settings, 'MEDIA_ROOT'):
            media_dir = settings.MEDIA_ROOT
        
        if not os.path.exists(media_dir):
            print("Media directory not found:", media_dir)
            return
        
        total_files = 0
        total_size = 0
        
        for root, dirs, files in os.walk(media_dir):
            for file in files:
                total_files += 1
                file_path = os.path.join(root, file)
                
                try:
                    size = os.path.getsize(file_path)
                    total_size += size
                    
                    if size > 10 * 1024 * 1024:  # >10MB
                        size_mb = size // (1024*1024)
                        self.warnings.append("LARGE MEDIA: " + file_path + " (" + str(size_mb) + "MB)")
                    
                    if file.startswith('.') or file.endswith(('.tmp', '.bak', '.old')):
                        self.warnings.append("TEMP FILE: " + file_path)
                        
                except:
                    pass
        
        print("Media files:", total_files)
        print("Total size:", total_size // (1024*1024), "MB")
    
    def find_junk_files(self):
        """Find junk files"""
        print("\n--- Finding junk files ---")
        
        junk_extensions = ['.pyc', '.pyo', '.tmp', '.bak', '.old', '.orig', '.swp']
        junk_dirs = ['__pycache__', '.git', 'node_modules']
        
        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if d not in junk_dirs]
            
            for file in files:
                file_path = os.path.join(root, file)
                
                # Check extensions
                for ext in junk_extensions:
                    if file.endswith(ext):
                        self.junk_files.append(file_path)
                        break
                
                # Check old files (6+ months)
                try:
                    mtime = os.path.getmtime(file_path)
                    if time.time() - mtime > 180 * 24 * 3600:
                        self.warnings.append("OLD FILE: " + file_path)
                except:
                    pass
        
        print("Junk files found:", len(self.junk_files))
    
    def check_database(self):
        """Check database models"""
        print("\n--- Checking database ---")
        
        if not DJANGO_OK:
            return
            
        try:
            from content.models import Article
            
            empty_count = Article.objects.filter(content__isnull=True).count()
            if empty_count > 0:
                self.warnings.append("Articles without content: " + str(empty_count))
            
            total_articles = Article.objects.count()
            print("Total articles:", total_articles)
            
        except ImportError:
            self.warnings.append("Cannot import content models")
        except Exception as e:
            self.warnings.append("DB check error: " + str(e))
    
    def check_urls(self):
        """Check URLs configuration"""
        print("\n--- Checking URLs ---")
        
        urls_files = [
            os.path.join(self.project_root, 'urls.py'),
            os.path.join(self.project_root, 'myapp', 'urls.py'),
            os.path.join(self.project_root, 'content', 'urls.py'),
        ]
        
        for urls_file in urls_files:
            if os.path.exists(urls_file):
                try:
                    with open(urls_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    url_patterns = re.findall(r"path\(['\"]([^'\"]*)['\"]", content)
                    print("URL patterns in " + urls_file + ":", len(url_patterns))
                    
                except Exception as e:
                    self.errors.append("URL file error " + urls_file + ": " + str(e))
    
    def check_settings(self):
        """Check Django settings"""
        print("\n--- Checking settings ---")
        
        if not DJANGO_OK:
            return
            
        # Check DEBUG
        if getattr(settings, 'DEBUG', False):
            self.warnings.append("DEBUG=True in production!")
        
        # Check ALLOWED_HOSTS
        allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', [])
        if not allowed_hosts or allowed_hosts == ['*']:
            self.warnings.append("ALLOWED_HOSTS not configured properly")
        
        # Check SECRET_KEY
        secret_key = getattr(settings, 'SECRET_KEY', '')
        if len(secret_key) < 30:
            self.errors.append("SECRET_KEY too short!")
    
    def run_check(self):
        """Run all checks"""
        print("="*60)
        print("DJANGO SITE CHECKER")
        print("="*60)
        
        self.check_templates()
        self.check_static_files()
        self.check_media_files()
        self.find_junk_files()
        self.check_database()
        self.check_urls()
        self.check_settings()
        
        self.print_results()
    
    def print_results(self):
        """Print check results"""
        print("\n" + "="*60)
        print("RESULTS")
        print("="*60)
        
        if self.errors:
            print("\nCRITICAL ERRORS (" + str(len(self.errors)) + "):")
            for i, error in enumerate(self.errors, 1):
                print("  " + str(i) + ". " + error)
        
        if self.warnings:
            print("\nWARNINGS (" + str(len(self.warnings)) + "):")
            for i, warning in enumerate(self.warnings[:15], 1):
                print("  " + str(i) + ". " + warning)
            if len(self.warnings) > 15:
                print("  ... and " + str(len(self.warnings) - 15) + " more warnings")
        
        if self.junk_files:
            print("\nJUNK FILES (" + str(len(self.junk_files)) + "):")
            for i, junk in enumerate(self.junk_files[:10], 1):
                rel_path = junk.replace(self.project_root, '.')
                print("  " + str(i) + ". " + rel_path)
            if len(self.junk_files) > 10:
                print("  ... and " + str(len(self.junk_files) - 10) + " more files")
        
        print("\nSUMMARY:")
        print("  Critical errors: " + str(len(self.errors)))
        print("  Warnings: " + str(len(self.warnings)))
        print("  Junk files: " + str(len(self.junk_files)))
        
        if not self.errors:
            print("\nGREAT! No critical errors found!")

if __name__ == "__main__":
    checker = SiteChecker()
    try:
        checker.run_check()
    except KeyboardInterrupt:
        print("\nCheck interrupted by user")
    except Exception as e:
        print("Critical error:", str(e))
        import traceback
        traceback.print_exc()
        