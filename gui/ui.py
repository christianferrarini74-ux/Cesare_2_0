import streamlit as st
from gui.models import MemoryEntry, MemoryTier

def render_memory_card(entry: MemoryEntry):
    """Disegna una card elegante per una voce di memoria."""
    tier_class = f"tier-{entry.tier.name[-1]}"
    tier_label = entry.tier.value
    
    with st.container():
        st.markdown(f"""
        <div class="memory-card">
            <span class="tier-badge {tier_class}">{tier_label}</span>
            <h3 style="margin: 10px 0 5px 0;">{entry.summary}</h3>
            <p style="color: #CCC; font-size: 0.95em;">{entry.content[:150]}{'...' if len(entry.content) > 150 else ''}</p>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
                <span style="font-size: 0.8em; color: #666;">{entry.timestamp.strftime('%d/%m/%Y %H:%M')}</span>
                {f'<span class="expiration-text">Scade tra {entry.expiration_days} giorni</span>' if entry.tier == MemoryTier.TIER_1 else ''}
                {f'<span style="color: #FFD700; font-weight: bold;">PERMANENTE</span>' if entry.tier == MemoryTier.TIER_2 else ''}
                {f'<span style="color: #FF4B4B; font-weight: bold;">SEME ERRORE</span>' if entry.tier == MemoryTier.TIER_3 else ''}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Ispeziona Dettagli", key=f"btn_{entry.id}"):
            st.session_state.selected_entry = entry
            st.rerun()

def render_detail_panel(entry: MemoryEntry):
    """Mostra il pannello laterale o centrale con i dettagli completi."""
    st.markdown(f"<h1 class='detail-header'>DETTAGLIO MEMORIA: {entry.id}</h1>", unsafe_allow_html=True)
    st.divider()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Contenuto Completo")
        st.info(entry.content)
        
        if entry.tier == MemoryTier.TIER_3:
            st.subheader("Analisi Evolutiva")
            st.error(f"**Errore Originale:**\n{entry.original_error}")
            st.markdown(f"""
            <div class="principle-box">
                <b style="color: #00FFA3;">Principio Correttivo:</b><br>
                {entry.corrective_principle}
            </div>
            """, unsafe_allow_html=True)
            
    with col2:
        st.subheader("Metadati")
        st.write(f"**Tier:** {entry.tier.value}")
        st.write(f"**Creato il:** {entry.timestamp.strftime('%Y-%m-%d %H:%M')}")
        
        if entry.expires_at:
            st.write(f"**Scadenza:** {entry.expires_at.strftime('%Y-%m-%d')}")
            
        st.write("**Tags:**")
        tag_cols = st.columns(len(entry.tags)) if entry.tags else []
        for i, tag in enumerate(entry.tags):
            with tag_cols[i]:
                st.button(f"#{tag}", disabled=True, key=f"tag_{entry.id}_{tag}")
            
        st.write(f"**Importanza:** {'⭐' * (entry.importance // 2)}")
        
    if st.button("⬅️ Torna alla lista"):
        st.session_state.selected_entry = None
        st.rerun()