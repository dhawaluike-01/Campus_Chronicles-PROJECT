document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const postForm = document.getElementById("postForm");
  const categorySelect = document.getElementById("category");
  const titleInput = document.getElementById("title");
  const messageInput = document.getElementById("message");
  const charCount = document.getElementById("charCount");
  const postsContainer = document.getElementById("postsContainer");
  const emptyState = document.getElementById("emptyState");
  const filterButtons = document.getElementById("filterButtons");
  const viewAllBtn = document.getElementById("viewAll");
  const viewPopularBtn = document.getElementById("viewPopular");

  const totalPostsEl = document.getElementById("totalPosts");
  const totalLikesEl = document.getElementById("totalLikes");
  const totalCommentsEl = document.getElementById("totalComments");
  const trendingCategoriesEl = document.getElementById("trendingCategories");
  const topPostsEl = document.getElementById("topPosts");

  let allPosts = [];
  let activeFilter = "all";
  let activeView = "all"; // 'all' or 'popular'

  // --- Helpers ---
  function escapeHtml(unsafe) {
    if (!unsafe && unsafe !== 0) return "";
    return String(unsafe)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function nl2br(str) {
    return str.replace(/\n/g, "<br>");
  }

  // --- Fetch and render posts ---
  async function fetchPosts() {
    try {
      const res = await fetch("/api/posts");
      const data = await res.json();
      allPosts = data.posts || [];
      renderPosts();
    } catch (err) {
      console.error("Failed to fetch posts:", err);
    }
  }



  async function toggleLike(postId, btn) {
    try {
        const response = await fetch(`/api/posts/${postId}/like`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();

        if (!response.ok) {
            alert(data.error || "Error occurred.");
            return;
        }

        // ✅ Update like count on success
        const likeCountElem = btn.querySelector('.like-count');
        if (likeCountElem) {
            likeCountElem.textContent = data.likes;
        }

        // ✅ Change button color or text based on message
        if (data.message === "Post liked successfully.") {
            btn.classList.add("liked");
            btn.textContent = `💖 Liked (${data.likes})`;
        } else if (data.message === "Like removed.") {
            btn.classList.remove("liked");
            btn.textContent = `❤️ Like (${data.likes})`;
        }

    } catch (error) {
        console.error("Like error:", error);
        alert("Unable to like post at the moment.");
    }
  }





  function renderPosts() {
    if (!postsContainer) return;

    let posts = [...allPosts];

    if (activeFilter !== "all") {
      posts = posts.filter(p => p.category === activeFilter);
    }

    if (activeView === "popular") {
      posts.sort((a, b) => b.likes - a.likes || new Date(b.created_at) - new Date(a.created_at));
    } else {
      posts.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    }

    postsContainer.innerHTML = "";

    if (!posts.length) {
      if (emptyState) emptyState.style.display = "block";
      return;
    } else if (emptyState) {
      emptyState.style.display = "none";
    }

    posts.forEach(post => {
      const card = document.createElement("div");
      card.className = "post-card";

      const titleHTML = post.title ? `<div class="post-title">${escapeHtml(post.title)}</div>` : "";
      const time = new Date(post.created_at).toLocaleString();

      card.innerHTML = `
        <div class="post-header">
          <div class="post-category">${escapeHtml(post.category)}</div>
          <div class="post-meta"><div class="post-time">${time}</div></div>
        </div>
        ${titleHTML}
        <div class="post-content">${nl2br(escapeHtml(post.message))}</div>

        <div class="post-footer">
          <div class="post-action like-action">
            <button class="like-btn" data-id="${post.id}">❤️ ${post.likes}</button>
          </div>
          <div class="post-action comment-action">
            <span>${post.comments.length} comments</span>
          </div>
        </div>

        <div class="comments-section" style="margin-top:16px;">
          <div class="comment-list" id="comments-${post.id}">
            ${post.comments.map(c => `<div class="comment">💬 ${escapeHtml(c.text)}</div>`).join("")}
          </div>
          <form class="comment-form" data-id="${post.id}" style="display:flex; gap:8px; margin-top:10px;">
            <input type="text" name="comment" placeholder="Write a comment..." required style="flex:1; padding:8px; border-radius:8px; border:1px solid #ddd;">
            <button type="submit" style="padding:8px 12px; border-radius:8px; border:none; background:#667eea; color:#fff; cursor:pointer;">Send</button>
          </form>
        </div>
      `;

      postsContainer.appendChild(card);
    });
  }

  // --- Post submission ---
  if (postForm) {
    postForm.addEventListener("submit", async e => {
      e.preventDefault();
      const payload = {
        category: categorySelect.value,
        title: titleInput.value.trim(),
        message: messageInput.value.trim()
      };

      if (!payload.category) return alert("Choose a category");
      if (!payload.message) return alert("Write your message");

      try {
        const res = await fetch("/api/posts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        if (res.status === 201) {
          postForm.reset();
          if (charCount) charCount.textContent = "0";
          await fetchPosts();
          await fetchStats();
          await fetchTrending();
        } else {
          const err = await res.json();
          alert(err.error || "Failed to post");
        }
      } catch (err) {
        console.error("Post error:", err);
        alert("Failed to post. Check console.");
      }
    });
  }

  if (messageInput && charCount) {
    messageInput.addEventListener("input", () => {
      charCount.textContent = messageInput.value.length;
    });
  }

  // --- Delegated like & comment ---
  if (postsContainer) {
    postsContainer.addEventListener("click", async e => {
      const likeBtn = e.target.closest(".like-btn");
      if (!likeBtn) return;
      const id = likeBtn.dataset.id;
      try {
        const res = await fetch(`/api/posts/${id}/like`, { method: "POST" });
        if (!res.ok) return;
        const data = await res.json();
        likeBtn.textContent = `❤️ ${data.likes}`;
        const post = allPosts.find(p => String(p.id) === String(id));
        if (post) post.likes = data.likes;
        await fetchStats();
      } catch (err) {
        console.error("Like error:", err);
      }
    });

    postsContainer.addEventListener("submit", async e => {
      if (!e.target.classList.contains("comment-form")) return;
      e.preventDefault();
      const postId = e.target.dataset.id;
      const input = e.target.querySelector('input[name="comment"]');
      const text = input.value.trim();
      if (!text) return;

      try {
        const res = await fetch(`/api/posts/${postId}/comment`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text })
        });
        if (res.status === 201) {
          const data = await res.json();
          const list = document.getElementById(`comments-${postId}`);
          if (list) list.insertAdjacentHTML('beforeend', `<div class="comment">💬 ${escapeHtml(data.text)}</div>`);
          input.value = "";
          const post = allPosts.find(p => String(p.id) === String(postId));
          if (post) post.comments.push({ text: data.text });
          await fetchStats();
        } else {
          const err = await res.json();
          alert(err.error || "Failed to comment");
        }
      } catch (err) {
        console.error("Comment error:", err);
      }
    });
  }

  // --- Filter buttons ---
  if (filterButtons) {
    filterButtons.addEventListener("click", e => {
      const btn = e.target.closest(".filter-btn");
      if (!btn) return;
      filterButtons.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      activeFilter = btn.dataset.filter || "all";
      renderPosts();
    });
  }

  // --- View toggle ---
  if (viewAllBtn && viewPopularBtn) {
    viewAllBtn.addEventListener("click", () => {
      activeView = "all";
      viewAllBtn.classList.add("active");
      viewPopularBtn.classList.remove("active");
      renderPosts();
    });
    viewPopularBtn.addEventListener("click", () => {
      activeView = "popular";
      viewPopularBtn.classList.add("active");
      viewAllBtn.classList.remove("active");
      renderPosts();
    });
  }


  // 
  async function submitPost() {
  const message = document.querySelector("#message").value;
  const title = document.querySelector("#title").value;
  const category = document.querySelector("#category").value;

  const response = await fetch("/api/posts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category, title, message })
  });

  const data = await response.json();

  if (!response.ok) {
    // 🚫 Show AI moderation reason to user
    alert(data.error + (data.reasons ? "\nReasons: " + data.reasons.join(", ") : ""));
    return;
  }

  alert("✅ Post created successfully!");
}



  // --- Fetch stats ---
  async function fetchStats() {
    if (!totalPostsEl && !totalLikesEl && !totalCommentsEl) return;
    try {
      const res = await fetch("/api/stats");
      const data = await res.json();
      if (totalPostsEl) totalPostsEl.innerText = data.posts_this_week;
      if (totalLikesEl) totalLikesEl.innerText = data.total_likes;
      if (totalCommentsEl) totalCommentsEl.innerText = data.total_comments;
    } catch (err) {
      console.error("Failed to fetch stats:", err);
    }
  }

  // --- Fetch trending & top posts ---
  async function fetchTrending() {
    if (!trendingCategoriesEl && !topPostsEl) return;
    try {
      const res = await fetch("/api/trending");
      const data = await res.json();

      if (trendingCategoriesEl) {
        trendingCategoriesEl.innerHTML = "";
        data.categories.forEach(cat => {
          const div = document.createElement("div");
          div.innerHTML = `${cat.category}: ${cat.count}`;
          trendingCategoriesEl.appendChild(div);
        });
      }

      if (topPostsEl) {
        topPostsEl.innerHTML = "";
        data.top_posts.forEach(post => {
          const div = document.createElement("div");
          div.innerHTML = `<strong>${post.title || 'No Title'}</strong><br>${post.message.substring(0, 50)}...`;
          topPostsEl.appendChild(div);
        });
      }
    } catch (err) {
      console.error("Failed to fetch trending:", err);
    }
  }

  // --- Init dashboard ---
  async function initDashboard() {
    await fetchPosts();
    await fetchStats();
    await fetchTrending();
  }

  initDashboard();

  // Polling
  setInterval(fetchPosts, 30000);
  setInterval(fetchStats, 60000);
  setInterval(fetchTrending, 60000);
});
