document.addEventListener('DOMContentLoaded', () => {
    // Start Page Logic
    const startForm = document.getElementById('startForm');
    if (startForm) {
        startForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(startForm);
            const data = Object.fromEntries(formData.entries());
            
            // Convert types
            data.candidates_per_iter = parseInt(data.candidates_per_iter);
            data.max_iters = parseInt(data.max_iters);
            data.dedup_threshold = parseFloat(data.dedup_threshold);
            data.lock_text = true;

            showLoading("Initializing Session...");

            try {
                const res = await fetch('/api/session/start', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                const json = await res.json();
                if (json.redirect_url) {
                    window.location.href = json.redirect_url;
                }
            } catch (err) {
                alert("Error starting session: " + err);
                hideLoading();
            }
        });
    }

    // Session Page Logic
    const nextBtn = document.getElementById('next-iter-btn');
    if (nextBtn) {
        nextBtn.addEventListener('click', handleNextIteration);
    }
});

let currentIter = typeof CURRENT_ITER !== 'undefined' ? CURRENT_ITER : 1;

async function handleNextIteration() {
    const bestRadio = document.querySelector('input[name="best_candidate"]:checked');
    if (!bestRadio) {
        alert("Please select a 'Best' candidate before proceeding.");
        return;
    }

    const bestId = bestRadio.value;
    const userNote = document.getElementById('user-note').value;
    
    // Collect ratings
    const ratings = {};
    document.querySelectorAll('.rating-input').forEach(input => {
        const candId = input.closest('.stars').dataset.cand;
        ratings[candId] = parseInt(input.value);
    });

    const payload = {
        iter: currentIter,
        ratings: ratings,
        best_id: bestId,
        user_note: userNote
    };

    showLoading("Generating Next Iteration (LLM + TTS)... This may take a minute.");

    try {
        const res = await fetch(`/api/session/${SESSION_ID}/iterate`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        
        if (!res.ok) throw new Error(await res.text());
        
        const data = await res.json();
        
        // Render next iteration
        renderNewIteration(data);
        hideLoading();

    } catch (err) {
        alert("Error: " + err);
        hideLoading();
    }
}

function renderNewIteration(data) {
    currentIter = data.iter;
    document.getElementById('iter-num').textContent = currentIter;
    
    // Update Best So Far
    if (data.best_so_far) {
        const container = document.getElementById('best-so-far-container');
        container.innerHTML = `
            <div class="audio-wrapper">
                <audio controls src="${data.best_so_far.audio_path}"></audio>
            </div>
            <p style="font-size:0.8rem; margin-top:0.5rem">${data.best_so_far.instruct}</p>
        `;
    }

    // Clear and Fill Candidates
    const grid = document.getElementById('candidates-container');
    grid.innerHTML = '';
    
    data.candidates.forEach(cand => {
        const card = document.createElement('div');
        card.className = 'candidate-card';
        card.dataset.id = cand.cand_id;
        card.innerHTML = `
            <div class="card-header">
                <span class="badge ${cand.type}">${cand.type}</span>
                <span class="cand-id">#${cand.cand_id}</span>
            </div>
            
            <div class="audio-wrapper">
                <audio controls src="${cand.audio_path}"></audio>
            </div>
            
            <div class="info">
                <details>
                    <summary>Instruct</summary>
                    <p class="text-sm">${cand.instruct}</p>
                </details>
                <p class="rationale"><strong>Rationale:</strong> ${cand.rationale}</p>
            </div>

            <div class="rating-area">
                <label>Rating (1-5):</label>
                <div class="stars" data-cand="${cand.cand_id}">
                    <input type="number" min="1" max="5" value="3" class="rating-input">
                </div>
            </div>

            <div class="selection-area">
                <label class="radio-label">
                    <input type="radio" name="best_candidate" value="${cand.cand_id}">
                    Select as Best
                </label>
            </div>
        `;
        grid.appendChild(card);
    });

    // Reset Inputs
    document.getElementById('user-note').value = '';
    window.scrollTo(0, 0);
}

function showLoading(msg) {
    const div = document.createElement('div');
    div.id = 'loading-overlay';
    div.className = 'loading-overlay';
    div.innerText = msg;
    document.body.appendChild(div);
}

function hideLoading() {
    const div = document.getElementById('loading-overlay');
    if (div) div.remove();
}
