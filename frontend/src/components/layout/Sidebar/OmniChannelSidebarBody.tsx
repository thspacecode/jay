import { useContext, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Flex, ScrollArea, Text } from '@radix-ui/themes'
import { ChannelListContext, ChannelListContextType, ChannelListItem } from '@/utils/channel/ChannelListProvider'
import {
    SidebarBadge,
    SidebarGroup,
    SidebarGroupItem,
    SidebarGroupLabel,
    SidebarGroupList,
    SidebarIcon,
    SidebarItem,
    SidebarViewMoreButton,
} from './SidebarComp'
import { UserListContext } from '@/utils/users/UserListProvider'
import { UserAvatar } from '@/components/common/UserAvatar'
import { useFetchUnreadMessageCount } from '@/hooks/useUnreadMessageCount'
import { useStickyState } from '@/hooks/useStickyState'
import { __ } from '@/utils/translations'
import { FaFacebook, FaLine } from 'react-icons/fa'

type OmniChannelItem = ChannelListItem & { unread_count: number }

interface ProviderGroup {
    provider?: string
    channels: OmniChannelItem[]
}

const PROVIDER_ICONS: Record<string, React.ReactNode> = {
    line: <FaLine className='text-[#06C755]' />,
    facebook: <FaFacebook className='text-[#1877F2]' />,
}

export const OmniChannelSidebarBody = () => {
    const { channels } = useContext(ChannelListContext) as ChannelListContextType
    const { workspaceID } = useParams()
    const unread_count = useFetchUnreadMessageCount()

    const channelsWithUnread = useMemo(() => {
        const workspaceChannels = channels.filter(c => c.workspace === workspaceID && !c.is_archived)
        return workspaceChannels.map(c => ({
            ...c,
            unread_count: unread_count?.message?.find(u => u.name === c.name)?.unread_count ?? 0,
        })) as OmniChannelItem[]
    }, [channels, workspaceID, unread_count])

    const unreadChannels = useMemo(() => channelsWithUnread.filter(c => c.unread_count > 0), [channelsWithUnread])

    const groupedChannels = useMemo(() => {
        const groups: Record<string, ProviderGroup> = {}
        channelsWithUnread.forEach(c => {
            const key = c.omni_channel_display_name ?? c.omni_channel_chat_provider ?? 'Other'
            if (!groups[key]) groups[key] = { provider: c.omni_channel_provider, channels: [] }
            groups[key].channels.push(c)
        })
        return groups
    }, [channelsWithUnread])

    return (
        <ScrollArea type="hover" scrollbars="vertical" className='h-[calc(100vh-4rem)]'>
            <Flex direction='column' gap='2' className='overflow-x-hidden pb-12 sm:pb-0' px='2'>
                {unreadChannels.length > 0 && (
                    <OmniProviderGroup
                        label={__("Unread")}
                        channels={unreadChannels}
                        storageKey="omni_unread"
                        showProvider
                    />
                )}
                {Object.entries(groupedChannels).map(([label, group]) => (
                    <OmniProviderGroup
                        key={label}
                        label={label}
                        channels={group.channels}
                        provider={group.provider}
                        storageKey={`omni_provider_${label}`}
                    />
                ))}
            </Flex>
        </ScrollArea>
    )
}

interface OmniProviderGroupProps {
    label: string
    channels: OmniChannelItem[]
    storageKey: string
    provider?: string
    showProvider?: boolean
}

const OmniProviderGroup = ({ label, channels, storageKey, provider, showProvider }: OmniProviderGroupProps) => {
    const [showData, setShowData] = useStickyState(true, storageKey)
    const toggle = () => setShowData((d: boolean) => !d)

    const ref = useRef<HTMLDivElement>(null)
    const [height, setHeight] = useState(ref?.current?.clientHeight ?? (showData ? channels.length * 44 : 0))

    useLayoutEffect(() => {
        setHeight(ref.current?.clientHeight ?? 0)
    }, [channels])

    const icon = provider ? PROVIDER_ICONS[provider] : null

    return (
        <SidebarGroup>
            <SidebarGroupItem className='gap-1 pl-1'>
                <Flex width='100%' justify='between' align='center' gap='2' pr='2' className='group'>
                    <Flex align='center' gap='2' width='100%' onClick={toggle} className='cursor-default select-none'>
                        {icon && <span className='flex items-center text-base'>{icon}</span>}
                        <SidebarGroupLabel>{label}</SidebarGroupLabel>
                    </Flex>
                    <SidebarViewMoreButton onClick={toggle} expanded={showData} />
                </Flex>
            </SidebarGroupItem>
            <SidebarGroup>
                <SidebarGroupList style={{ height: showData ? height : 0 }}>
                    <div ref={ref} className='flex gap-0.5 flex-col'>
                        {channels.map(channel => (
                            <OmniChannelItemRow
                                key={channel.name}
                                channel={channel}
                                showProvider={showProvider}
                            />
                        ))}
                    </div>
                </SidebarGroupList>
            </SidebarGroup>
        </SidebarGroup>
    )
}

const OmniChannelItemRow = ({ channel, showProvider }: { channel: OmniChannelItem, showProvider?: boolean }) => {
    const { users } = useContext(UserListContext)
    const { channelID } = useParams()

    const customerUser = useMemo(() => users.find(u => u.name === channel.omni_channel_raven_user), [users, channel.omni_channel_raven_user])

    const displayName = customerUser?.full_name ?? channel.channel_name
    const showUnread = channel.unread_count > 0 && channelID !== channel.name

    return (
        <SidebarItem to={channel.name} className='py-1 px-2'>
            <SidebarIcon>
                <UserAvatar
                    src={customerUser?.user_image}
                    alt={displayName}
                    size={{ initial: '2', md: '1' }}
                />
            </SidebarIcon>
            <Flex direction='column' flexGrow='1' style={{ minWidth: 0 }}>
                <Flex justify='between' align='center' width='100%'>
                    <Text
                        size={{ initial: '3', md: '2' }}
                        className='text-ellipsis line-clamp-1'
                        weight={showUnread ? 'bold' : 'medium'}
                    >
                        {displayName}
                    </Text>
                    {showUnread && <SidebarBadge>{channel.unread_count}</SidebarBadge>}
                </Flex>
                {showProvider && (channel.omni_channel_display_name ?? channel.omni_channel_chat_provider) && (
                    <Text size='1' color='gray' className='text-ellipsis line-clamp-1'>
                        {channel.omni_channel_display_name ?? channel.omni_channel_chat_provider}
                    </Text>
                )}
            </Flex>
        </SidebarItem>
    )
}
