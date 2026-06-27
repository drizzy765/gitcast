def show_popup(on_submit, on_dismiss):
    """
    Tkinter popup fallback/mock.
    Immediately submits a default thought to run the pipeline.
    """
    import threading
    
    def run():
        print("[Gitcast] Mock popup triggered.")
        on_submit("Captured via hotkey trigger")
        
    threading.Thread(target=run, daemon=True).start()
