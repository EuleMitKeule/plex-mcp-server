import json
import os
from typing import List, Optional

import aiohttp
from mcp.types import AnyFunction
from plexapi.exceptions import NotFound

from plex_mcp_server.const import PermissionsType
from plex_mcp_server.tools.tools import PlexMcpTools


class PlexPlaylistTools(PlexMcpTools):
    """Tools for managing Plex playlists."""

    def __init__(
        self,
        plex_url: str,
        plex_token: str,
        permissions: PermissionsType,
    ) -> None:
        """Initialize the Plex Playlist Tools."""
        tools: list[AnyFunction] = [
            self.playlist_list,
            self.playlist_get_contents,
        ]
        if permissions in [PermissionsType.WRITE, PermissionsType.DELETE]:
            tools.extend(
                [
                    self.playlist_create,
                    self.playlist_edit,
                    self.playlist_upload_poster,
                    self.playlist_copy_to_user,
                    self.playlist_add_to,
                ]
            )
        if permissions == PermissionsType.DELETE:
            tools.extend(
                [
                    self.playlist_delete,
                    self.playlist_remove_from,
                ]
            )

        super().__init__(plex_url, plex_token, permissions, tools)

    async def playlist_list(
        self, library_name: Optional[str] = None, content_type: Optional[str] = None
    ) -> str:
        """List all playlists on the Plex server.

        Args:
            library_name: Optional library name to filter playlists from
            content_type: Optional content type to filter playlists (audio, video, photo)
        """
        try:
            plex = self._plex_client.connection
            playlists = []

            # Filter by content type if specified
            if content_type:
                valid_types = ["audio", "video", "photo"]
                if content_type.lower() not in valid_types:
                    return json.dumps(
                        {
                            "error": f"Invalid content type. Valid types are: {', '.join(valid_types)}"
                        },
                        indent=4,
                    )
                playlists = plex.playlists(playlistType=content_type.lower())
            else:
                playlists = plex.playlists()

            # Filter by library if specified
            if library_name:
                try:
                    library = plex.library.section(library_name)
                    # Use the section's playlists method directly
                    if content_type:
                        playlists = library.playlists(playlistType=content_type.lower())
                    else:
                        playlists = library.playlists()
                except NotFound:
                    return json.dumps(
                        {"error": f"Library '{library_name}' not found"}, indent=4
                    )

            # Format playlist data (lightweight version - no items)
            playlist_data = []
            for playlist in playlists:
                try:
                    playlist_data.append(
                        {
                            "title": playlist.title,
                            "key": playlist.key,
                            "ratingKey": playlist.ratingKey,
                            "type": playlist.playlistType,
                            "summary": playlist.summary
                            if hasattr(playlist, "summary")
                            else "",
                            "duration": playlist.duration
                            if hasattr(playlist, "duration")
                            else None,
                            "item_count": playlist.leafCount
                            if hasattr(playlist, "leafCount")
                            else None,
                        }
                    )
                except Exception as item_error:
                    # If there's an error with a specific playlist, include error info
                    playlist_data.append(
                        {
                            "title": getattr(playlist, "title", "Unknown"),
                            "key": getattr(playlist, "key", "Unknown"),
                            "error": str(item_error),
                        }
                    )

            return json.dumps(playlist_data, indent=4)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=4)

    async def playlist_create(
        self,
        playlist_title: str,
        item_titles: List[str],
        library_name: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> str:
        """Create a new playlist with specified items.

        Args:
            playlist_title: Title for the new playlist
            item_titles: List of media titles to include in the playlist
            library_name: Optional library name to limit search to
            summary: Optional summary description for the playlist
        """
        try:
            plex = self._plex_client.connection
            items = []

            # Search for items in all libraries or specific library
            for title in item_titles:
                found = False
                search_scope = (
                    plex.library.section(library_name) if library_name else plex.library
                )

                # Search for the item
                search_results = search_scope.search(title=title)

                if search_results:
                    items.append(search_results[0])
                    found = True

                if not found:
                    return json.dumps(
                        {"status": "error", "message": f"Item '{title}' not found"},
                        indent=4,
                    )

            if not items:
                return json.dumps(
                    {"status": "error", "message": "No items found for the playlist"},
                    indent=4,
                )

            # Create the playlist
            playlist = plex.createPlaylist(
                title=playlist_title, items=items, summary=summary
            )

            return json.dumps(
                {
                    "status": "success",
                    "message": f"Playlist '{playlist_title}' created successfully",
                    "data": {
                        "title": playlist.title,
                        "key": playlist.key,
                        "ratingKey": playlist.ratingKey,
                        "item_count": len(items),
                    },
                },
                indent=4,
            )
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}, indent=4)

    async def playlist_edit(
        self,
        playlist_title: Optional[str] = None,
        playlist_id: Optional[int] = None,
        new_title: Optional[str] = None,
        new_summary: Optional[str] = None,
    ) -> str:
        """Edit a playlist's details such as title and summary.

        Args:
            playlist_title: Title of the playlist to edit (optional if playlist_id is provided)
            playlist_id: ID of the playlist to edit (optional if playlist_title is provided)
            new_title: Optional new title for the playlist
            new_summary: Optional new summary for the playlist
        """
        try:
            plex = self._plex_client.connection

            # Validate that at least one identifier is provided
            if not playlist_id and not playlist_title:
                return json.dumps(
                    {"error": "Either playlist_id or playlist_title must be provided"},
                    indent=4,
                )

            # Find the playlist
            playlist = None
            original_title = None

            # If playlist_id is provided, use it to directly fetch the playlist
            if playlist_id:
                try:
                    # Try fetching by ratingKey first
                    try:
                        playlist = plex.fetchItem(playlist_id)
                    except Exception:
                        # If that fails, try finding by key in all playlists
                        all_playlists = plex.playlists()
                        playlist = next(
                            (p for p in all_playlists if p.ratingKey == playlist_id),
                            None,
                        )

                    if not playlist:
                        return json.dumps(
                            {"error": f"Playlist with ID '{playlist_id}' not found"},
                            indent=4,
                        )
                    original_title = playlist.title
                except Exception as e:
                    return json.dumps(
                        {"error": f"Error fetching playlist by ID: {str(e)}"}, indent=4
                    )
            else:
                # Search by title
                playlists = plex.playlists()
                matching_playlists = [
                    p for p in playlists if p.title.lower() == playlist_title.lower()
                ]

                if not matching_playlists:
                    return json.dumps(
                        {"error": f"No playlist found with title '{playlist_title}'"},
                        indent=4,
                    )

                # If multiple matching playlists, return list of matches with IDs
                if len(matching_playlists) > 1:
                    matches = []
                    for p in matching_playlists:
                        matches.append(
                            {
                                "title": p.title,
                                "id": p.ratingKey,
                                "type": p.playlistType,
                                "item_count": p.leafCount
                                if hasattr(p, "leafCount")
                                else len(p.items()),
                            }
                        )

                    # Return as a direct array like playlist_list
                    return json.dumps(matches, indent=4)

                playlist = matching_playlists[0]
                original_title = playlist.title

            # Track changes
            changes = []

            # Update title if provided
            if new_title and new_title != playlist.title:
                playlist.edit(title=new_title)
                changes.append(f"title from '{original_title}' to '{new_title}'")

            # Update summary if provided
            if new_summary is not None:  # Allow empty summaries
                current_summary = (
                    playlist.summary if hasattr(playlist, "summary") else ""
                )
                if new_summary != current_summary:
                    playlist.edit(summary=new_summary)
                    changes.append("summary")

            if not changes:
                return json.dumps(
                    {
                        "updated": False,
                        "title": playlist.title,
                        "message": "No changes made to the playlist",
                    },
                    indent=4,
                )

            return json.dumps(
                {"updated": True, "title": playlist.title, "changes": changes}, indent=4
            )
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=4)

    async def playlist_upload_poster(
        self,
        playlist_title: Optional[str] = None,
        playlist_id: Optional[int] = None,
        poster_url: Optional[str] = None,
        poster_filepath: Optional[str] = None,
    ) -> str:
        """Upload a poster image for a playlist.

        Args:
            playlist_title: Title of the playlist (optional if playlist_id is provided)
            playlist_id: ID of the playlist (optional if playlist_title is provided)
            poster_url: URL to poster image to upload
            poster_filepath: Local file path to poster image to upload
        """
        try:
            plex = self._plex_client.connection

            # Validate that at least one identifier is provided
            if not playlist_id and not playlist_title:
                return json.dumps(
                    {"error": "Either playlist_id or playlist_title must be provided"},
                    indent=4,
                )

            # Validate that exactly one poster source is provided
            if not poster_url and not poster_filepath:
                return json.dumps(
                    {"error": "Either poster_url or poster_filepath must be provided"},
                    indent=4,
                )

            if poster_url and poster_filepath:
                return json.dumps(
                    {"error": "Provide either poster_url or poster_filepath, not both"},
                    indent=4,
                )

            # Find the playlist
            playlist = None

            # If playlist_id is provided, use it to directly fetch the playlist
            if playlist_id:
                try:
                    # Try fetching by ratingKey first
                    try:
                        playlist = plex.fetchItem(playlist_id)
                    except Exception:
                        # If that fails, try finding by key in all playlists
                        all_playlists = plex.playlists()
                        playlist = next(
                            (p for p in all_playlists if p.ratingKey == playlist_id),
                            None,
                        )

                    if not playlist:
                        return json.dumps(
                            {"error": f"Playlist with ID '{playlist_id}' not found"},
                            indent=4,
                        )
                except Exception as e:
                    return json.dumps(
                        {"error": f"Error fetching playlist by ID: {str(e)}"}, indent=4
                    )
            else:
                # Search by title
                playlists = plex.playlists()
                matching_playlists = [
                    p for p in playlists if p.title.lower() == playlist_title.lower()
                ]

                if not matching_playlists:
                    return json.dumps(
                        {"error": f"No playlist found with title '{playlist_title}'"},
                        indent=4,
                    )

                # If multiple matching playlists, return list of matches with IDs
                if len(matching_playlists) > 1:
                    matches = []
                    for p in matching_playlists:
                        matches.append(
                            {
                                "title": p.title,
                                "id": p.ratingKey,
                                "type": p.playlistType,
                                "item_count": p.leafCount
                                if hasattr(p, "leafCount")
                                else len(p.items()),
                            }
                        )

                    return json.dumps(
                        {
                            "error": "Multiple playlists found with that title. Please use playlist_id instead.",
                            "matches": matches,
                        },
                        indent=4,
                    )

                playlist = matching_playlists[0]

            # Get poster data
            poster_data = None

            if poster_url:
                # Download poster from URL
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(poster_url) as response:
                            if response.status == 200:
                                poster_data = await response.read()
                            else:
                                return json.dumps(
                                    {
                                        "error": f"Failed to download poster from URL. Status: {response.status}"
                                    },
                                    indent=4,
                                )
                except Exception as e:
                    return json.dumps(
                        {"error": f"Error downloading poster: {str(e)}"}, indent=4
                    )

            elif poster_filepath:
                # Read poster from local file
                if not os.path.exists(poster_filepath):
                    return json.dumps(
                        {"error": f"Poster file not found: {poster_filepath}"}, indent=4
                    )

                try:
                    with open(poster_filepath, "rb") as f:
                        poster_data = f.read()
                except Exception as e:
                    return json.dumps(
                        {"error": f"Error reading poster file: {str(e)}"}, indent=4
                    )

            # Upload poster
            try:
                playlist.uploadPoster(poster_data)
                return json.dumps(
                    {
                        "status": "success",
                        "message": f"Poster uploaded successfully for playlist '{playlist.title}'",
                    },
                    indent=4,
                )
            except Exception as e:
                return json.dumps(
                    {"error": f"Error uploading poster: {str(e)}"}, indent=4
                )

        except Exception as e:
            return json.dumps({"error": str(e)}, indent=4)

    async def playlist_copy_to_user(
        self,
        playlist_title: Optional[str] = None,
        playlist_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> str:
        """Copy a playlist to another user's account.

        Args:
            playlist_title: Title of the playlist to copy (optional if playlist_id is provided)
            playlist_id: ID of the playlist to copy (optional if playlist_title is provided)
            username: Username to copy the playlist to
        """
        try:
            plex = self._plex_client.connection

            # Validate that at least one identifier is provided
            if not playlist_id and not playlist_title:
                return json.dumps(
                    {"error": "Either playlist_id or playlist_title must be provided"},
                    indent=4,
                )

            if not username:
                return json.dumps({"error": "Username must be provided"}, indent=4)

            # Find the playlist
            playlist = None

            # If playlist_id is provided, use it to directly fetch the playlist
            if playlist_id:
                try:
                    # Try fetching by ratingKey first
                    try:
                        playlist = plex.fetchItem(playlist_id)
                    except Exception:
                        # If that fails, try finding by key in all playlists
                        all_playlists = plex.playlists()
                        playlist = next(
                            (p for p in all_playlists if p.ratingKey == playlist_id),
                            None,
                        )

                    if not playlist:
                        return json.dumps(
                            {"error": f"Playlist with ID '{playlist_id}' not found"},
                            indent=4,
                        )
                except Exception as e:
                    return json.dumps(
                        {"error": f"Error fetching playlist by ID: {str(e)}"}, indent=4
                    )
            else:
                # Search by title
                playlists = plex.playlists()
                matching_playlists = [
                    p for p in playlists if p.title.lower() == playlist_title.lower()
                ]

                if not matching_playlists:
                    return json.dumps(
                        {"error": f"No playlist found with title '{playlist_title}'"},
                        indent=4,
                    )

                # If multiple matching playlists, return list of matches with IDs
                if len(matching_playlists) > 1:
                    matches = []
                    for p in matching_playlists:
                        matches.append(
                            {
                                "title": p.title,
                                "id": p.ratingKey,
                                "type": p.playlistType,
                                "item_count": p.leafCount
                                if hasattr(p, "leafCount")
                                else len(p.items()),
                            }
                        )

                    return json.dumps(
                        {
                            "error": "Multiple playlists found with that title. Please use playlist_id instead.",
                            "matches": matches,
                        },
                        indent=4,
                    )

                playlist = matching_playlists[0]

            # Find the target user
            try:
                target_user = plex.myPlexAccount().user(username)
            except Exception:
                # If direct user lookup fails, try searching through account users
                try:
                    account = plex.myPlexAccount()
                    users = account.users()
                    target_user = next(
                        (
                            user
                            for user in users
                            if user.username.lower() == username.lower()
                        ),
                        None,
                    )
                    if not target_user:
                        return json.dumps(
                            {"error": f"User '{username}' not found"}, indent=4
                        )
                except Exception as e:
                    return json.dumps(
                        {"error": f"Error finding user '{username}': {str(e)}"},
                        indent=4,
                    )

            # Copy playlist to user
            try:
                playlist.copyToUser(target_user)
                return json.dumps(
                    {
                        "status": "success",
                        "message": f"Playlist '{playlist.title}' copied to user '{username}' successfully",
                    },
                    indent=4,
                )
            except Exception as e:
                return json.dumps(
                    {"error": f"Error copying playlist to user: {str(e)}"}, indent=4
                )

        except Exception as e:
            return json.dumps({"error": str(e)}, indent=4)

    async def playlist_add_to(
        self,
        playlist_title: Optional[str] = None,
        playlist_id: Optional[int] = None,
        item_titles: Optional[List[str]] = None,
        item_ids: Optional[List[int]] = None,
    ) -> str:
        """Add items to an existing playlist.

        Args:
            playlist_title: Title of the playlist (optional if playlist_id is provided)
            playlist_id: ID of the playlist (optional if playlist_title is provided)
            item_titles: List of media titles to add to the playlist
            item_ids: List of media IDs to add to the playlist
        """
        try:
            plex = self._plex_client.connection

            # Validate that at least one identifier is provided
            if not playlist_id and not playlist_title:
                return json.dumps(
                    {"error": "Either playlist_id or playlist_title must be provided"},
                    indent=4,
                )

            # Validate that items are provided
            if not item_titles and not item_ids:
                return json.dumps(
                    {"error": "Either item_titles or item_ids must be provided"},
                    indent=4,
                )

            if item_titles and item_ids:
                return json.dumps(
                    {"error": "Provide either item_titles or item_ids, not both"},
                    indent=4,
                )

            # Find the playlist
            playlist = None

            # If playlist_id is provided, use it to directly fetch the playlist
            if playlist_id:
                try:
                    # Try fetching by ratingKey first
                    try:
                        playlist = plex.fetchItem(playlist_id)
                    except Exception:
                        # If that fails, try finding by key in all playlists
                        all_playlists = plex.playlists()
                        playlist = next(
                            (p for p in all_playlists if p.ratingKey == playlist_id),
                            None,
                        )

                    if not playlist:
                        return json.dumps(
                            {"error": f"Playlist with ID '{playlist_id}' not found"},
                            indent=4,
                        )
                except Exception as e:
                    return json.dumps(
                        {"error": f"Error fetching playlist by ID: {str(e)}"}, indent=4
                    )
            else:
                # Search by title
                playlists = plex.playlists()
                matching_playlists = [
                    p for p in playlists if p.title.lower() == playlist_title.lower()
                ]

                if not matching_playlists:
                    return json.dumps(
                        {"error": f"No playlist found with title '{playlist_title}'"},
                        indent=4,
                    )

                # If multiple matching playlists, return list of matches with IDs
                if len(matching_playlists) > 1:
                    matches = []
                    for p in matching_playlists:
                        matches.append(
                            {
                                "title": p.title,
                                "id": p.ratingKey,
                                "type": p.playlistType,
                                "item_count": p.leafCount
                                if hasattr(p, "leafCount")
                                else len(p.items()),
                            }
                        )

                    return json.dumps(
                        {
                            "error": "Multiple playlists found with that title. Please use playlist_id instead.",
                            "matches": matches,
                        },
                        indent=4,
                    )

                playlist = matching_playlists[0]

            # Prepare items to add
            items_to_add = []

            if item_titles:
                # Search for items by title
                for title in item_titles:
                    search_results = plex.library.search(title=title)
                    if search_results:
                        items_to_add.append(search_results[0])
                    else:
                        return json.dumps(
                            {"error": f"Item '{title}' not found"}, indent=4
                        )

            elif item_ids:
                # Fetch items by ID
                for item_id in item_ids:
                    try:
                        item = plex.fetchItem(item_id)
                        items_to_add.append(item)
                    except Exception:
                        return json.dumps(
                            {"error": f"Item with ID '{item_id}' not found"}, indent=4
                        )

            if not items_to_add:
                return json.dumps(
                    {"error": "No valid items found to add to the playlist"}, indent=4
                )

            # Add items to playlist
            try:
                playlist.addItems(items_to_add)
                return json.dumps(
                    {
                        "status": "success",
                        "message": f"Added {len(items_to_add)} items to playlist '{playlist.title}'",
                    },
                    indent=4,
                )
            except Exception as e:
                return json.dumps(
                    {"error": f"Error adding items to playlist: {str(e)}"}, indent=4
                )

        except Exception as e:
            return json.dumps({"error": str(e)}, indent=4)

    async def playlist_remove_from(
        self,
        playlist_title: Optional[str] = None,
        playlist_id: Optional[int] = None,
        item_titles: Optional[List[str]] = None,
    ) -> str:
        """Remove items from a playlist by title.

        Args:
            playlist_title: Title of the playlist (optional if playlist_id is provided)
            playlist_id: ID of the playlist (optional if playlist_title is provided)
            item_titles: List of media titles to remove from the playlist
        """
        try:
            plex = self._plex_client.connection

            # Validate that at least one identifier is provided
            if not playlist_id and not playlist_title:
                return json.dumps(
                    {"error": "Either playlist_id or playlist_title must be provided"},
                    indent=4,
                )

            # Validate that items are provided
            if not item_titles:
                return json.dumps({"error": "item_titles must be provided"}, indent=4)

            # Find the playlist
            playlist = None

            # If playlist_id is provided, use it to directly fetch the playlist
            if playlist_id:
                try:
                    # Try fetching by ratingKey first
                    try:
                        playlist = plex.fetchItem(playlist_id)
                    except Exception:
                        # If that fails, try finding by key in all playlists
                        all_playlists = plex.playlists()
                        playlist = next(
                            (p for p in all_playlists if p.ratingKey == playlist_id),
                            None,
                        )

                    if not playlist:
                        return json.dumps(
                            {"error": f"Playlist with ID '{playlist_id}' not found"},
                            indent=4,
                        )
                except Exception as e:
                    return json.dumps(
                        {"error": f"Error fetching playlist by ID: {str(e)}"}, indent=4
                    )
            else:
                # Search by title
                playlists = plex.playlists()
                matching_playlists = [
                    p for p in playlists if p.title.lower() == playlist_title.lower()
                ]

                if not matching_playlists:
                    return json.dumps(
                        {"error": f"No playlist found with title '{playlist_title}'"},
                        indent=4,
                    )

                # If multiple matching playlists, return list of matches with IDs
                if len(matching_playlists) > 1:
                    matches = []
                    for p in matching_playlists:
                        matches.append(
                            {
                                "title": p.title,
                                "id": p.ratingKey,
                                "type": p.playlistType,
                                "item_count": p.leafCount
                                if hasattr(p, "leafCount")
                                else len(p.items()),
                            }
                        )

                    return json.dumps(
                        {
                            "error": "Multiple playlists found with that title. Please use playlist_id instead.",
                            "matches": matches,
                        },
                        indent=4,
                    )

                playlist = matching_playlists[0]

            # Get current playlist items
            current_items = playlist.items()
            items_to_remove = []

            # Find items to remove by title
            for title_to_remove in item_titles:
                found_items = [
                    item
                    for item in current_items
                    if item.title.lower() == title_to_remove.lower()
                ]
                if found_items:
                    items_to_remove.extend(found_items)
                else:
                    return json.dumps(
                        {"error": f"Item '{title_to_remove}' not found in playlist"},
                        indent=4,
                    )

            if not items_to_remove:
                return json.dumps(
                    {"error": "No items found to remove from the playlist"}, indent=4
                )

            # Remove items from playlist
            try:
                playlist.removeItems(items_to_remove)
                return json.dumps(
                    {
                        "status": "success",
                        "message": f"Removed {len(items_to_remove)} items from playlist '{playlist.title}'",
                    },
                    indent=4,
                )
            except Exception as e:
                return json.dumps(
                    {"error": f"Error removing items from playlist: {str(e)}"}, indent=4
                )

        except Exception as e:
            return json.dumps({"error": str(e)}, indent=4)

    async def playlist_delete(
        self, playlist_title: Optional[str] = None, playlist_id: Optional[int] = None
    ) -> str:
        """Delete a playlist permanently.

        Args:
            playlist_title: Title of the playlist to delete (optional if playlist_id is provided)
            playlist_id: ID of the playlist to delete (optional if playlist_title is provided)
        """
        try:
            plex = self._plex_client.connection

            # Validate that at least one identifier is provided
            if not playlist_id and not playlist_title:
                return json.dumps(
                    {"error": "Either playlist_id or playlist_title must be provided"},
                    indent=4,
                )

            # Find the playlist
            playlist = None

            # If playlist_id is provided, use it to directly fetch the playlist
            if playlist_id:
                try:
                    # Try fetching by ratingKey first
                    try:
                        playlist = plex.fetchItem(playlist_id)
                    except Exception:
                        # If that fails, try finding by key in all playlists
                        all_playlists = plex.playlists()
                        playlist = next(
                            (p for p in all_playlists if p.ratingKey == playlist_id),
                            None,
                        )

                    if not playlist:
                        return json.dumps(
                            {"error": f"Playlist with ID '{playlist_id}' not found"},
                            indent=4,
                        )
                except Exception as e:
                    return json.dumps(
                        {"error": f"Error fetching playlist by ID: {str(e)}"}, indent=4
                    )
            else:
                # Search by title
                playlists = plex.playlists()
                matching_playlists = [
                    p for p in playlists if p.title.lower() == playlist_title.lower()
                ]

                if not matching_playlists:
                    return json.dumps(
                        {"error": f"No playlist found with title '{playlist_title}'"},
                        indent=4,
                    )

                # If multiple matching playlists, return list of matches with IDs
                if len(matching_playlists) > 1:
                    matches = []
                    for p in matching_playlists:
                        matches.append(
                            {
                                "title": p.title,
                                "id": p.ratingKey,
                                "type": p.playlistType,
                                "item_count": p.leafCount
                                if hasattr(p, "leafCount")
                                else len(p.items()),
                            }
                        )

                    return json.dumps(
                        {
                            "error": "Multiple playlists found with that title. Please use playlist_id instead.",
                            "matches": matches,
                        },
                        indent=4,
                    )

                playlist = matching_playlists[0]

            # Store playlist title before deletion
            playlist_title_for_message = playlist.title

            # Delete the playlist
            try:
                playlist.delete()
                return json.dumps(
                    {
                        "status": "success",
                        "message": f"Playlist '{playlist_title_for_message}' deleted successfully",
                    },
                    indent=4,
                )
            except Exception as e:
                return json.dumps(
                    {"error": f"Error deleting playlist: {str(e)}"}, indent=4
                )

        except Exception as e:
            return json.dumps({"error": str(e)}, indent=4)

    async def playlist_get_contents(
        self, playlist_title: Optional[str] = None, playlist_id: Optional[int] = None
    ) -> str:
        """Get the contents of a playlist.

        Args:
            playlist_title: Title of the playlist (optional if playlist_id is provided)
            playlist_id: ID of the playlist (optional if playlist_title is provided)
        """
        try:
            plex = self._plex_client.connection

            # Validate that at least one identifier is provided
            if not playlist_id and not playlist_title:
                return json.dumps(
                    {"error": "Either playlist_id or playlist_title must be provided"},
                    indent=4,
                )

            # Find the playlist
            playlist = None

            # If playlist_id is provided, use it to directly fetch the playlist
            if playlist_id:
                try:
                    # Try fetching by ratingKey first
                    try:
                        playlist = plex.fetchItem(playlist_id)
                    except Exception:
                        # If that fails, try finding by key in all playlists
                        all_playlists = plex.playlists()
                        playlist = next(
                            (p for p in all_playlists if p.ratingKey == playlist_id),
                            None,
                        )

                    if not playlist:
                        return json.dumps(
                            {"error": f"Playlist with ID '{playlist_id}' not found"},
                            indent=4,
                        )
                except Exception as e:
                    return json.dumps(
                        {"error": f"Error fetching playlist by ID: {str(e)}"}, indent=4
                    )
            else:
                # Search by title
                playlists = plex.playlists()
                matching_playlists = [
                    p for p in playlists if p.title.lower() == playlist_title.lower()
                ]

                if not matching_playlists:
                    return json.dumps(
                        {"error": f"No playlist found with title '{playlist_title}'"},
                        indent=4,
                    )

                # If multiple matching playlists, return list of matches with IDs
                if len(matching_playlists) > 1:
                    matches = []
                    for p in matching_playlists:
                        matches.append(
                            {
                                "title": p.title,
                                "id": p.ratingKey,
                                "type": p.playlistType,
                                "item_count": p.leafCount
                                if hasattr(p, "leafCount")
                                else len(p.items()),
                            }
                        )

                    return json.dumps(
                        {
                            "error": "Multiple playlists found with that title. Please use playlist_id instead.",
                            "matches": matches,
                        },
                        indent=4,
                    )

                playlist = matching_playlists[0]

            # Get playlist contents
            try:
                items = playlist.items()

                # Format the playlist data
                playlist_data = {
                    "title": playlist.title,
                    "ratingKey": playlist.ratingKey,
                    "type": playlist.playlistType,
                    "summary": playlist.summary if hasattr(playlist, "summary") else "",
                    "duration": playlist.duration
                    if hasattr(playlist, "duration")
                    else None,
                    "item_count": len(items),
                    "items": [],
                }

                # Add item details
                for item in items:
                    try:
                        item_data = {
                            "title": item.title,
                            "ratingKey": item.ratingKey,
                            "type": item.type if hasattr(item, "type") else "unknown",
                        }

                        # Add additional fields based on item type
                        if hasattr(item, "year"):
                            item_data["year"] = item.year
                        if hasattr(item, "duration"):
                            item_data["duration"] = item.duration
                        if hasattr(item, "artist") and item.artist:
                            item_data["artist"] = item.artist.title
                        if hasattr(item, "album") and item.album:
                            item_data["album"] = item.album.title
                        if hasattr(item, "grandparentTitle"):
                            item_data["series"] = item.grandparentTitle
                        if hasattr(item, "parentTitle"):
                            item_data["season"] = item.parentTitle

                        playlist_data["items"].append(item_data)
                    except Exception as item_error:
                        # If there's an error with a specific item, include error info
                        playlist_data["items"].append(
                            {
                                "title": getattr(item, "title", "Unknown"),
                                "error": str(item_error),
                            }
                        )

                return json.dumps(playlist_data, indent=4)
            except Exception as e:
                return json.dumps(
                    {"error": f"Error getting playlist contents: {str(e)}"}, indent=4
                )

        except Exception as e:
            return json.dumps({"error": str(e)}, indent=4)
