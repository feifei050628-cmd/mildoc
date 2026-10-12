// 对话浏览
(function() {
    const ORIGIN = {
        CUSTOMER: 3,
        SYSTEM: 4,
        HUMAN: 5,
        AI: 666
    };

    const ORIGIN_LABEL = {
        3: '客户',
        4: '系统',
        5: '人工',
        666: 'AI'
    };

    const ORIGIN_CLASS = {
        3: 'msg-origin-customer',
        4: 'msg-origin-system',
        5: 'msg-origin-human',
        666: 'msg-origin-ai'
    };

    function formatSendTime(timestamp) {
        if (!timestamp) return '';
        const d = new Date(timestamp * 1000);
        return d.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }

    function isCustomerMessage(origin) {
        return origin === ORIGIN.CUSTOMER;
    }

    function buildQueryParams(external_userid, start_id, limit) {
        const params = new URLSearchParams();
        if (external_userid) params.set('external_userid', external_userid);
        if (start_id != null && start_id !== '') params.set('start_id', start_id);
        params.set('limit', limit);
        return params.toString();
    }

    function renderMessage(msg) {
        const alignRight = !isCustomerMessage(msg.origin);
        const originClass = ORIGIN_CLASS[msg.origin] || '';
        const originLabel = ORIGIN_LABEL[msg.origin] || '未知';
        const senderId = msg.origin === ORIGIN.CUSTOMER ? msg.external_userid : msg.servicer_userid;
        const rowClass = alignRight ? 'conversation-row conversation-row-right' : 'conversation-row conversation-row-left';
        const bubbleClass = 'conversation-bubble ' + originClass;

        return `
            <div class="${rowClass}">
                <div class="${bubbleClass}">
                    <div class="conversation-meta">
                        <span class="conversation-time">${formatSendTime(msg.send_time)}</span>
                        <span class="conversation-origin conversation-origin-${msg.origin}">${originLabel}</span>
                    </div>
                    <div class="conversation-content">${escapeHtml(msg.content || '(无内容)')}</div>
                    <div class="conversation-sender">${msg.origin === ORIGIN.CUSTOMER ? 'external_userid: ' : 'servicer_userid: '}${escapeHtml(senderId || '-')}</div>
                </div>
            </div>
        `;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function renderList(messages, append) {
        const listEl = document.getElementById('conversation-list');
        if (!append) listEl.innerHTML = '';
        if (messages.length === 0 && !append) {
            listEl.innerHTML = '<div class="loading">暂无消息</div>';
            return;
        }
        const fragment = document.createDocumentFragment();
        messages.forEach(function(msg) {
            const wrap = document.createElement('div');
            wrap.innerHTML = renderMessage(msg).trim();
            fragment.appendChild(wrap.firstChild);
        });
        if (append) {
            listEl.appendChild(fragment);
        } else {
            listEl.innerHTML = '';
            listEl.appendChild(fragment);
        }
    }

    function syncUrl(external_userid, start_id, limit) {
        const qs = buildQueryParams(external_userid, start_id, limit);
        const url = '/conversation' + (qs ? '?' + qs : '');
        if (window.location.pathname + (window.location.search || '') !== url) {
            window.history.replaceState({}, '', url);
        }
    }

    function readParamsFromUrl() {
        const params = new URLSearchParams(window.location.search);
        return {
            external_userid: params.get('external_userid') || '',
            start_id: params.get('start_id') || '',
            limit: params.get('limit') || '20'
        };
    }

    function initFromUrl() {
        const p = readParamsFromUrl();
        const externalInput = document.getElementById('filter-external-userid');
        const limitSelect = document.getElementById('filter-limit');
        if (externalInput) externalInput.value = p.external_userid;
        if (limitSelect) limitSelect.value = p.limit;
        return p;
    }

    function loadMessages(append) {
        const external_userid = document.getElementById('filter-external-userid').value.trim() || undefined;
        const limit = parseInt(document.getElementById('filter-limit').value, 10) || 20;
        let start_id = -1;
        if (append && window.conversationBrowser && window.conversationBrowser.next_start_id != null) {
            start_id = window.conversationBrowser.next_start_id;
        }
        const listEl = document.getElementById('conversation-list');
        if (!append) Utils.showLoading(listEl);
        const qs = buildQueryParams(external_userid, start_id >= 0 ? start_id : '', limit);
        Utils.ajax('/api/conversation/messages?' + qs)
            .then(function(data) {
                renderList(data.messages, append);
                if (!append && data.messages.length === 0) return;
                window.conversationBrowser = window.conversationBrowser || {};
                window.conversationBrowser.next_start_id = data.next_start_id;
                const loadMoreWrap = document.getElementById('load-more-wrap');
                if (loadMoreWrap) {
                    loadMoreWrap.style.display = data.messages.length >= limit && data.next_start_id != null ? 'block' : 'none';
                }
                syncUrl(external_userid, undefined, limit);
            })
            .catch(function(err) {
                Utils.showError(listEl, err.message);
            });
    }

    function onQuery() {
        loadMessages(false);
    }

    function onLoadMore() {
        loadMessages(true);
    }

    function bindEvents() {
        document.getElementById('btn-query').addEventListener('click', onQuery);
        var loadMoreBtn = document.getElementById('btn-load-more');
        if (loadMoreBtn) loadMoreBtn.addEventListener('click', onLoadMore);
    }

    function init() {
        initFromUrl();
        bindEvents();
        loadMessages(false);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
