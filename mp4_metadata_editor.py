import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import requests
from pathlib import Path

try:
    from mutagen.mp4 import MP4
except ImportError:
    MP4 = None

TMDB_API_KEY = "e2f93ae17129525263a684bb6de5c06d"  # Free public key


class TMDbScraper:
    def __init__(self):
        self.base_url = "https://api.themoviedb.org/3"
        self.api_key = TMDB_API_KEY

    def search_movies(self, title):
        """Search TMDb for movies"""
        try:
            url = f"{self.base_url}/search/movie"
            params = {
                "api_key": self.api_key,
                "query": title,
                "page": 1
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            results = []
            for movie in data.get('results', [])[:10]:
                results.append({
                    'id': movie.get('id'),
                    'title': movie.get('title', ''),
                    'year': movie.get('release_date', '')[:4] if movie.get('release_date') else 'N/A'
                })
            return results
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def get_movie_info(self, movie_id):
        """Fetch full movie info from TMDb"""
        try:
            url = f"{self.base_url}/movie/{movie_id}"
            params = {
                "api_key": self.api_key,
                "append_to_response": "credits,release_dates"
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            directors = []
            producers = []
            composers = []
            actors = []

            crew = data.get('credits', {}).get('crew', [])
            for person in crew:
                job = person.get('job', '')
                if job == 'Director':
                    directors.append({'name': person.get('name', '')})
                elif job == 'Producer':
                    producers.append({'name': person.get('name', '')})
                elif job == 'Original Music Composer':
                    composers.append({'name': person.get('name', '')})

            cast = data.get('credits', {}).get('cast', [])[:5]
            for person in cast:
                actors.append({'name': person.get('name', '')})

            genres = [g.get('name', '') for g in data.get('genres', [])[:5]]

            # Get parental rating (US rating preferred)
            parental_rating = 'Not Rated'
            for release in data.get('release_dates', {}).get('results', []):
                if release.get('iso_3166_1') == 'US':
                    parental_rating = release.get('release_dates', [{}])[0].get('certification', 'Not Rated')
                    break

            return {
                'id': movie_id,
                'title': data.get('title', ''),
                'description': data.get('overview', '')[:300],
                'datePublished': data.get('release_date', '')[:4],
                'genre': genres,
                'directors': directors,
                'producers': producers,
                'composers': composers,
                'actors': actors,
                'parental_rating': parental_rating,
                'aggregateRating': {
                    'ratingValue': str(round(data.get('vote_average', 0), 1))
                },
            }
        except Exception as e:
            print(f"Fetch error: {e}")
            return None


class MP4Handler:
    @staticmethod
    def write_metadata(filepath, movie_info):
        """Write movie info to MP4"""
        if not MP4:
            messagebox.showerror("Error", "mutagen not installed: pip install mutagen")
            return False

        try:
            audio = MP4(filepath)
            if audio.tags is None:
                audio.add_tags()

            tags = audio.tags
            tags['\xa9nam'] = [movie_info.get('title', '')]

            actors = ', '.join([a['name'] for a in movie_info.get('actors', [])])
            if actors:
                tags['\xa9ART'] = [actors]

            directors = ', '.join([d['name'] for d in movie_info.get('directors', [])])
            if directors:
                tags['\xa9dir'] = [directors]

            producers = ', '.join([p['name'] for p in movie_info.get('producers', [])])
            if producers:
                tags['\xa9prd'] = [producers]

            composers = ', '.join([c['name'] for c in movie_info.get('composers', [])])
            if composers:
                tags['\xa9wrt'] = [composers]

            genres = movie_info.get('genre', [])
            if genres:
                tags['\xa9gen'] = genres

            desc = movie_info.get('description', '')
            if desc:
                tags['\xa9cmt'] = [desc[:500]]

            year = movie_info.get('datePublished', '')
            if year:
                tags['\xa9day'] = [year]

            rating = movie_info.get('aggregateRating', {}).get('ratingValue', '')
            parental_rating = movie_info.get('parental_rating', '')
            rating_str = f"TMDb: {rating}/10"
            if parental_rating and parental_rating != 'Not Rated':
                rating_str += f" | Rated: {parental_rating}"
            if rating:
                tags['cprt'] = [rating_str]

            audio.save()
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Write failed: {str(e)}")
            return False


class MetaScraperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("THE MetaScraper™")
        self.root.geometry("900x700")

        self.scraper = TMDbScraper()
        self.current_file = None
        self.current_movie_info = None
        self.search_results = []

        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        ttk.Label(main_frame, text="THE MetaScraper™", font=("Arial", 16, "bold")).grid(row=0, column=0, columnspan=3, pady=10)
        ttk.Label(main_frame, text="(Powered by The Movie Database)", font=("Arial", 9)).grid(row=0, column=2, sticky=tk.E)

        ttk.Button(main_frame, text="Select MP4", command=self.select_file).grid(row=1, column=0, pady=5)
        self.file_label = ttk.Label(main_frame, text="No file selected", foreground="gray")
        self.file_label.grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=10)

        ttk.Separator(main_frame, orient=tk.HORIZONTAL).grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        ttk.Label(main_frame, text="Search Movie:", font=("Arial", 10, "bold")).grid(row=3, column=0, columnspan=3, sticky=tk.W)

        search_frame = ttk.Frame(main_frame)
        search_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        self.search_entry = ttk.Entry(search_frame, width=40)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind('<Return>', lambda e: self.search_movies())

        ttk.Button(search_frame, text="Search", command=self.search_movies).pack(side=tk.LEFT)

        self.search_status = ttk.Label(main_frame, text="", foreground="blue")
        self.search_status.grid(row=5, column=0, columnspan=3, sticky=tk.W, padx=5)

        ttk.Label(main_frame, text="Results:", font=("Arial", 10, "bold")).grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=(10, 5))

        list_frame = ttk.Frame(main_frame)
        list_frame.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.results_listbox = tk.Listbox(list_frame, height=8, yscrollcommand=scrollbar.set)
        self.results_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.results_listbox.yview)
        self.results_listbox.bind('<Double-Button-1>', lambda e: self.select_result())

        ttk.Button(main_frame, text="Fetch Selected", command=self.select_result).grid(row=8, column=0, columnspan=3, pady=5)

        ttk.Separator(main_frame, orient=tk.HORIZONTAL).grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        ttk.Label(main_frame, text="Movie Info:", font=("Arial", 10, "bold")).grid(row=10, column=0, columnspan=3, sticky=tk.W)

        self.info_text = tk.Text(main_frame, height=10, width=80)
        self.info_text.grid(row=11, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=12, column=0, columnspan=3, pady=10)

        ttk.Button(button_frame, text="Write to MP4", command=self.write_metadata).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear", command=self.clear_form).pack(side=tk.LEFT, padx=5)

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(7, weight=1)
        main_frame.rowconfigure(11, weight=1)

    def select_file(self):
        filepath = filedialog.askopenfilename(
            title="Select MP4",
            filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")]
        )
        if filepath:
            self.current_file = filepath
            self.file_label.config(text=Path(filepath).name, foreground="black")
            self.search_entry.delete(0, tk.END)
            self.search_entry.insert(0, Path(filepath).stem)
            self.search_movies()

    def search_movies(self):
        query = self.search_entry.get().strip()
        if not query:
            messagebox.showwarning("Warning", "Enter a movie title")
            return

        self.search_status.config(text="Searching...", foreground="blue")
        self.results_listbox.delete(0, tk.END)

        thread = threading.Thread(target=self._search_worker, args=(query,), daemon=True)
        thread.start()

    def _search_worker(self, query):
        try:
            results = self.scraper.search_movies(query)
            self.search_results = results
            self.results_listbox.delete(0, tk.END)

            for result in results:
                self.results_listbox.insert(tk.END, f"{result['title']} ({result['year']})")

            if results:
                self.search_status.config(text=f"Found {len(results)} results", foreground="green")
                self.results_listbox.selection_set(0)
            else:
                self.search_status.config(text="No results", foreground="red")
        except Exception as e:
            self.search_status.config(text=f"Error: {str(e)}", foreground="red")

    def select_result(self):
        selection = self.results_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select a movie")
            return

        result = self.search_results[selection[0]]
        self.search_status.config(text="Loading...", foreground="blue")

        thread = threading.Thread(target=self._fetch_worker, args=(result['id'],), daemon=True)
        thread.start()

    def _fetch_worker(self, movie_id):
        try:
            info = self.scraper.get_movie_info(movie_id)
            if info:
                self.current_movie_info = info
                self._display_movie_info(info)
                self.search_status.config(text="Loaded ✓", foreground="green")
            else:
                self.search_status.config(text="Failed to load", foreground="red")
        except Exception as e:
            self.search_status.config(text=f"Error: {str(e)}", foreground="red")

    def _display_movie_info(self, info):
        self.info_text.delete(1.0, tk.END)

        text = f"Title: {info.get('title', 'N/A')}\n"
        text += f"Year: {info.get('datePublished', 'N/A')}\n"

        parental_rating = info.get('parental_rating', '')
        if parental_rating and parental_rating != 'Not Rated':
            text += f"Rating (US): {parental_rating}\n"

        rating = info.get('aggregateRating', {}).get('ratingValue', '')
        if rating:
            text += f"TMDb Score: {rating}/10\n"

        genres = info.get('genre', [])
        if genres:
            text += f"Genres: {', '.join(genres)}\n"

        directors = info.get('directors', [])
        if directors:
            text += f"Directors: {', '.join([d['name'] for d in directors])}\n"

        producers = info.get('producers', [])
        if producers:
            text += f"Producers: {', '.join([p['name'] for p in producers])}\n"

        composers = info.get('composers', [])
        if composers:
            text += f"Composers: {', '.join([c['name'] for c in composers])}\n"

        actors = info.get('actors', [])
        if actors:
            text += f"Cast: {', '.join([a['name'] for a in actors])}\n"

        desc = info.get('description', '')
        if desc:
            text += f"\n{desc}\n"

        self.info_text.insert(1.0, text)

    def write_metadata(self):
        if not self.current_file:
            messagebox.showwarning("Warning", "Select an MP4 file")
            return
        if not self.current_movie_info:
            messagebox.showwarning("Warning", "Fetch movie info first")
            return

        if MP4Handler.write_metadata(self.current_file, self.current_movie_info):
            messagebox.showinfo("Success", "Metadata written to MP4! ✓")
        else:
            messagebox.showerror("Error", "Failed to write metadata")

    def clear_form(self):
        self.current_file = None
        self.current_movie_info = None
        self.file_label.config(text="No file selected", foreground="gray")
        self.search_entry.delete(0, tk.END)
        self.results_listbox.delete(0, tk.END)
        self.info_text.delete(1.0, tk.END)
        self.search_status.config(text="")


if __name__ == "__main__":
    root = tk.Tk()
    app = MetaScraperGUI(root)
    root.mainloop()
